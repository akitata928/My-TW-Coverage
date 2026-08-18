# Vendored dependencies

`d3.v7.min.js` — D3 7.9.0, ISC licence, copied verbatim from the npm package `d3@7`.

Vendored rather than loaded from a CDN so `network/index.html` opens from `file://`
with no network access, which is how it is normally used. Refresh with:

```bash
npm pack d3@7 && tar -xzO -f d3-7.*.tgz package/dist/d3.min.js > network/vendor/d3.v7.min.js
```
