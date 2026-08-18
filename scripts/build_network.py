"""
build_network.py — Build the directed, typed supply-chain graph.

Edges come from relations.extract_relations, so they carry direction and kind
(supplies / competes / mentions) rather than mere co-occurrence. Co-occurrence
could only say two names appear together; this says who sells to whom.

Nearly every edge has weight 1 because one report asserts it. Weight 2 means
both companies' reports state the same relationship — mutual corroboration —
so weight is drawn as emphasis, not used as a filter. Filtering is by node
degree instead, which is what keeps the picture readable.

Outputs network/graph_data.json and network/index.html, which loads D3 from
network/vendor/ so it works from file:// with no network access.

Usage:
  python scripts/build_network.py              # top 300 nodes by degree
  python scripts/build_network.py --top 100    # smaller, clearer
  python scripts/build_network.py --top 0      # every node (slow to render)
"""

import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    PROJECT_ROOT, REPORTS_DIR, setup_stdout,
    WIKILINK_RE, classify_wikilink, CATEGORY_COLORS, CATEGORY_LABELS,
)
from relations import extract_relations, SUPPLIES, COMPETES, MENTIONS

NETWORK_DIR = os.path.join(PROJECT_ROOT, "network")

DEFAULT_TOP = 300

KIND_COLORS = {SUPPLIES: "#4fbfae", COMPETES: "#e07a5f", MENTIONS: "#6b7a8f"}
KIND_LABELS = {SUPPLIES: "供應 →", COMPETES: "競爭", MENTIONS: "提及"}


def scan_graph(top_n=DEFAULT_TOP):
    """Return (nodes, edges) for the directed relation graph."""
    mentions = Counter()
    tickers = {}
    weights = Counter()

    for root, _, files in os.walk(REPORTS_DIR):
        for f in sorted(files):
            m = re.match(r"^(\d{4})_(.+)\.md$", f)
            if not m:
                continue
            ticker, company = m.group(1), m.group(2)
            tickers[company] = ticker

            with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                head = fh.read().split("## 財務概況")[0]

            mentions.update(set(WIKILINK_RE.findall(head)))
            for r in extract_relations(head, company):
                weights[(r.source, r.target, r.kind)] += 1

    degree = Counter()
    for source, target, _ in weights:
        degree[source] += 1
        degree[target] += 1

    keep = set(degree) if not top_n else {n for n, _ in degree.most_common(top_n)}

    edges = [
        {"source": s, "target": t, "kind": k, "weight": w}
        for (s, t, k), w in weights.items()
        if s in keep and t in keep
    ]
    active = {e["source"] for e in edges} | {e["target"] for e in edges}

    nodes = []
    for name in sorted(active):
        category = classify_wikilink(name)
        node = {
            "id": name,
            "count": mentions[name],
            "degree": degree[name],
            "category": category,
            "color": CATEGORY_COLORS[category],
        }
        if name in tickers:
            node["ticker"] = tickers[name]
        nodes.append(node)

    return nodes, edges


def build_html(nodes, edges):
    """Generate the self-contained D3 view of the directed graph."""
    graph_json = json.dumps({"nodes": nodes, "links": edges}, ensure_ascii=False)

    present = {n["category"] for n in nodes}
    legend_items = "".join(
        f'<div class="key"><span class="dot" style="background:{CATEGORY_COLORS[k]}"></span>'
        f"<span>{CATEGORY_LABELS[k]}</span></div>"
        for k in CATEGORY_COLORS if k in present
    )
    kind_toggles = "".join(
        f'<label class="kind"><input type="checkbox" data-kind="{k}" checked>'
        f'<span class="bar" style="background:{KIND_COLORS[k]}"></span>{KIND_LABELS[k]}</label>'
        for k in (SUPPLIES, COMPETES, MENTIONS)
    )

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<title>台股供應鏈有向圖</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #1a1a2e; color: #eee; overflow: hidden; }}
  .panel {{ position: fixed; z-index: 10; background: rgba(26,26,46,0.95);
            padding: 14px 16px; border-radius: 10px; border: 1px solid #333; }}
  #controls {{ top: 12px; left: 12px; }}
  #controls h2 {{ font-size: 15px; margin-bottom: 10px; }}
  #controls label {{ font-size: 13px; display: block; margin: 8px 0 2px; }}
  #controls input[type=range] {{ width: 190px; }}
  #controls input[type=text] {{ width: 190px; padding: 4px 8px; background: #2a2a4e;
            border: 1px solid #444; color: #eee; border-radius: 4px; }}
  label.kind {{ display: flex; align-items: center; gap: 6px; font-size: 13px; margin: 4px 0; }}
  label.kind .bar {{ width: 16px; height: 3px; border-radius: 2px; }}
  #legend {{ bottom: 12px; left: 12px; display: flex; flex-wrap: wrap; gap: 4px 14px; }}
  .key {{ display: flex; align-items: center; gap: 6px; font-size: 13px; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  #tooltip {{ position: fixed; background: rgba(0,0,0,0.92); color: #fff; padding: 8px 14px;
              border-radius: 6px; font-size: 13px; pointer-events: none; display: none;
              z-index: 20; border: 1px solid #555; max-width: 320px; line-height: 1.6; }}
  #stats {{ top: 12px; right: 12px; font-size: 13px; }}
  svg {{ width: 100vw; height: 100vh; }}
  hr {{ border: none; border-top: 1px solid #333; margin: 10px 0; }}
</style>
</head>
<body>
<div id="controls" class="panel">
  <h2>供應鏈有向圖</h2>
  <label>顯示節點數：<span id="topVal">80</span></label>
  <input type="range" id="topSlider" min="20" max="{len(nodes)}" value="80">
  <hr>
  {kind_toggles}
  <hr>
  <label>搜尋</label>
  <input type="text" id="search" placeholder="台積電, NVIDIA, CoWoS">
</div>
<div id="legend" class="panel">{legend_items}</div>
<div id="tooltip"></div>
<div id="stats" class="panel"></div>
<svg></svg>

<script src="vendor/d3.v7.min.js"></script>
<script>
const fullData = {graph_json};
const KIND_COLORS = {json.dumps(KIND_COLORS)};
const KIND_LABELS = {json.dumps(KIND_LABELS, ensure_ascii=False)};
const CATEGORY_LABELS = {json.dumps(CATEGORY_LABELS, ensure_ascii=False)};
const width = window.innerWidth, height = window.innerHeight;

const svg = d3.select("svg");
svg.append("defs").selectAll("marker")
  .data(Object.keys(KIND_COLORS)).join("marker")
    .attr("id", d => "arrow-" + d)
    .attr("viewBox", "0 -5 10 10").attr("refX", 10).attr("refY", 0)
    .attr("markerWidth", 7).attr("markerHeight", 7).attr("orient", "auto")
  .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", d => KIND_COLORS[d]);

const g = svg.append("g");
svg.call(d3.zoom().scaleExtent([0.1, 8]).on("zoom", e => g.attr("transform", e.transform)));

const tooltip = d3.select("#tooltip");
let simulation, linkG, nodeG, labelG, rScale;

function activeKinds() {{
  return new Set(d3.selectAll("#controls input[type=checkbox]").nodes()
    .filter(c => c.checked).map(c => c.dataset.kind));
}}

function render() {{
  const topN = +d3.select("#topSlider").property("value");
  const kinds = activeKinds();
  const ranked = [...fullData.nodes].sort((a, b) => b.degree - a.degree).slice(0, topN);
  const allowed = new Set(ranked.map(n => n.id));

  const links = fullData.links.filter(l =>
    kinds.has(l.kind) &&
    allowed.has(l.source.id || l.source) && allowed.has(l.target.id || l.target));

  const activeIds = new Set();
  links.forEach(l => {{ activeIds.add(l.source.id || l.source); activeIds.add(l.target.id || l.target); }});
  const nodes = ranked.filter(n => activeIds.has(n.id));

  d3.select("#stats").html(`節點 ${{nodes.length}} ｜ 有向邊 ${{links.length}}`);
  g.selectAll("*").remove();

  const maxCount = d3.max(nodes, d => d.count) || 1;
  rScale = d3.scaleSqrt().domain([1, maxCount]).range([4, 34]);

  simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(110).strength(0.25))
    .force("charge", d3.forceManyBody().strength(-320))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => rScale(d.count) + 3));

  linkG = g.append("g").selectAll("line").data(links).join("line")
    .attr("stroke", d => KIND_COLORS[d.kind])
    .attr("stroke-opacity", d => d.weight > 1 ? 0.85 : 0.35)
    .attr("stroke-width", d => d.weight > 1 ? 2.5 : 1)
    .attr("marker-end", d => "url(#arrow-" + d.kind + ")");

  nodeG = g.append("g").selectAll("circle").data(nodes).join("circle")
    .attr("r", d => rScale(d.count)).attr("fill", d => d.color)
    .attr("stroke", "#fff").attr("stroke-width", 0.5).attr("opacity", 0.9)
    .call(d3.drag().on("start", dragStart).on("drag", dragging).on("end", dragEnd))
    .on("mouseover", (e, d) => {{ showTooltip(d); highlightNeighbors(d); }})
    .on("mousemove", e => tooltip.style("left", e.pageX+14+"px").style("top", e.pageY-20+"px"))
    .on("mouseout", () => {{ tooltip.style("display", "none"); resetHighlight(); }});

  labelG = g.append("g").selectAll("text").data(nodes.filter(d => d.count >= 15)).join("text")
    .text(d => d.id).attr("font-size", d => Math.max(9, Math.min(14, rScale(d.count) * 0.7)))
    .attr("fill", "#ccc").attr("text-anchor", "middle").attr("dy", d => rScale(d.count) + 12)
    .style("pointer-events", "none");

  simulation.on("tick", () => {{
    // Stop the line at the edge of the target circle so the arrowhead sits
    // outside it rather than being hidden underneath.
    linkG.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => {{
        const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
        const len = Math.hypot(dx, dy) || 1;
        return d.target.x - dx / len * (rScale(d.target.count) + 5);
      }})
      .attr("y2", d => {{
        const dx = d.target.x - d.source.x, dy = d.target.y - d.source.y;
        const len = Math.hypot(dx, dy) || 1;
        return d.target.y - dy / len * (rScale(d.target.count) + 5);
      }});
    nodeG.attr("cx", d => d.x).attr("cy", d => d.y);
    labelG.attr("x", d => d.x).attr("y", d => d.y);
  }});
}}

function showTooltip(d) {{
  // Read the full edge list, not the drawn subgraph: the panel would otherwise
  // report a node's upstream as whatever survived the current node limit.
  const up = [], down = [];
  for (const l of fullData.links) {{
    if (l.kind !== "supplies") continue;
    const s = l.source.id || l.source, t = l.target.id || l.target;
    if (t === d.id) up.push(s);
    if (s === d.id) down.push(t);
  }}
  const line = (label, arr) => arr.length
    ? `<br><b>${{label}}</b>（${{arr.length}}）：${{arr.slice(0, 6).join("、")}}${{arr.length > 6 ? " …" : ""}}` : "";
  tooltip.style("display", "block").html(
    `<b>${{d.id}}</b>${{d.ticker ? " (" + d.ticker + ")" : ""}}`
    + `<br>${{CATEGORY_LABELS[d.category]}} ｜ 提及 ${{d.count}} ｜ 連結 ${{d.degree}}`
    + line("上游", up) + line("下游", down));
}}

function highlightNeighbors(d) {{
  const neighbors = new Set([d.id]);
  linkG.each(function(l) {{
    if (l.source.id === d.id) neighbors.add(l.target.id);
    if (l.target.id === d.id) neighbors.add(l.source.id);
  }});
  nodeG.attr("opacity", n => neighbors.has(n.id) ? 1 : 0.08);
  linkG.attr("stroke-opacity", l => (l.source.id===d.id||l.target.id===d.id) ? 0.9 : 0.03);
  labelG.attr("opacity", n => neighbors.has(n.id) ? 1 : 0.08);
}}

function resetHighlight() {{
  nodeG.attr("opacity", 0.9);
  linkG.attr("stroke-opacity", d => d.weight > 1 ? 0.85 : 0.35);
  labelG.attr("opacity", 1);
}}

function dragStart(e, d) {{ if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }}
function dragging(e, d) {{ d.fx = e.x; d.fy = e.y; }}
function dragEnd(e, d) {{ if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }}

d3.select("#topSlider").on("input", function() {{
  d3.select("#topVal").text(this.value);
  render();
}});
d3.selectAll("#controls input[type=checkbox]").on("change", render);
d3.select("#search").on("input", function() {{
  const q = this.value.toLowerCase();
  if (!q) {{ resetHighlight(); return; }}
  const match = nodeG.data().find(n => n.id.toLowerCase().includes(q));
  if (match) {{ showTooltip(match); highlightNeighbors(match); }}
}});

render();
</script>
</body>
</html>"""


def main():
    setup_stdout()

    args = sys.argv[1:]
    top_n = DEFAULT_TOP
    if "--top" in args:
        top_n = int(args[args.index("--top") + 1])

    os.makedirs(NETWORK_DIR, exist_ok=True)

    print(f"Building directed relation graph (top {top_n or 'all'} nodes by degree)...")
    nodes, edges = scan_graph(top_n=top_n)
    kinds = Counter(e["kind"] for e in edges)
    corroborated = sum(1 for e in edges if e["weight"] > 1)
    print(f"Graph: {len(nodes)} nodes, {len(edges)} directed edges")
    print(f"  by kind: {dict(kinds)}")
    print(f"  asserted by both sides: {corroborated}")

    json_path = os.path.join(NETWORK_DIR, "graph_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"nodes": nodes, "links": edges}, f, ensure_ascii=False, indent=2)
    print(f"Saved: {json_path}")

    html_path = os.path.join(NETWORK_DIR, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(nodes, edges))
    print(f"Saved: {html_path}")
    print("\nOpen network/index.html in a browser.")


if __name__ == "__main__":
    main()
