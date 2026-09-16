-- Phase 3A: multi-industry XBRL financial facts and local analysis schema.
-- Raw facts are immutable; semantic tables are versioned projections.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issuers (
    ticker TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    industry_family TEXT NOT NULL CHECK (industry_family IN
        ('general_industrial','financial_holding','bank','insurance','securities','unknown')),
    institution_type TEXT,
    parent_ticker TEXT REFERENCES issuers(ticker),
    classification_source TEXT,
    effective_from TEXT,
    effective_to TEXT
);

CREATE TABLE IF NOT EXISTS raw_documents (
    raw_document_id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL REFERENCES issuers(ticker),
    report_period TEXT NOT NULL,
    report_year INTEGER,
    report_quarter INTEGER CHECK (report_quarter IS NULL OR report_quarter BETWEEN 1 AND 4),
    consolidation_scope TEXT NOT NULL CHECK (consolidation_scope IN ('consolidated','individual','unknown')),
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    taxonomy_version TEXT,
    parser_version TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (ticker, report_period, consolidation_scope, raw_sha256)
);

CREATE TABLE IF NOT EXISTS xbrl_contexts (
    context_id INTEGER PRIMARY KEY,
    raw_document_id INTEGER NOT NULL REFERENCES raw_documents(raw_document_id) ON DELETE CASCADE,
    context_ref TEXT NOT NULL,
    entity_scheme TEXT,
    entity_identifier TEXT,
    period_kind TEXT NOT NULL CHECK (period_kind IN ('instant','duration','unknown')),
    period_start TEXT,
    period_end TEXT,
    period_instant TEXT,
    period_role TEXT NOT NULL CHECK (period_role IN ('current','comparative','unknown')),
    dimensions_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE (raw_document_id, context_ref)
);

CREATE TABLE IF NOT EXISTS xbrl_units (
    unit_id INTEGER PRIMARY KEY,
    raw_document_id INTEGER NOT NULL REFERENCES raw_documents(raw_document_id) ON DELETE CASCADE,
    unit_ref TEXT NOT NULL,
    measure TEXT,
    numerator TEXT,
    denominator TEXT,
    unit_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (raw_document_id, unit_ref)
);

CREATE TABLE IF NOT EXISTS taxonomy_concepts (
    concept_id INTEGER PRIMARY KEY,
    namespace TEXT NOT NULL,
    concept_qname TEXT NOT NULL,
    local_name TEXT NOT NULL,
    label_zh_tw TEXT,
    label_en TEXT,
    balance TEXT,
    period_type TEXT,
    taxonomy_version TEXT NOT NULL,
    UNIQUE (concept_qname, taxonomy_version)
);

CREATE TABLE IF NOT EXISTS xbrl_facts (
    fact_id INTEGER PRIMARY KEY,
    raw_document_id INTEGER NOT NULL REFERENCES raw_documents(raw_document_id) ON DELETE CASCADE,
    concept_id INTEGER NOT NULL REFERENCES taxonomy_concepts(concept_id),
    context_id INTEGER NOT NULL REFERENCES xbrl_contexts(context_id),
    unit_id INTEGER REFERENCES xbrl_units(unit_id),
    raw_value TEXT,
    normalized_value TEXT,
    raw_unit TEXT,
    normalized_unit TEXT,
    decimals TEXT,
    value_status TEXT NOT NULL CHECK (value_status IN ('present','missing')),
    missing_value_reason TEXT,
    dimensions_json TEXT NOT NULL DEFAULT '[]',
    fact_sha256 TEXT NOT NULL,
    UNIQUE (raw_document_id, fact_sha256)
);

CREATE TABLE IF NOT EXISTS concept_mappings (
    concept_mapping_id INTEGER PRIMARY KEY,
    source_qname TEXT NOT NULL,
    canonical_concept TEXT NOT NULL,
    industry_family TEXT NOT NULL CHECK (industry_family IN
        ('general_industrial','financial_holding','bank','insurance','securities','unknown')),
    taxonomy_version TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    confidence TEXT NOT NULL CHECK (confidence IN ('high','medium','low','unknown')),
    mapping_status TEXT NOT NULL CHECK (mapping_status IN ('verified','provisional','unknown')),
    notes TEXT,
    UNIQUE (source_qname, industry_family, taxonomy_version, mapping_version)
);

CREATE TABLE IF NOT EXISTS statement_templates (
    template_id INTEGER PRIMARY KEY,
    template_name TEXT NOT NULL,
    industry_family TEXT NOT NULL CHECK (industry_family IN
        ('general_industrial','financial_holding','bank','insurance','securities','unknown')),
    statement_type TEXT NOT NULL,
    canonical_concept TEXT NOT NULL,
    requiredness TEXT NOT NULL CHECK (requiredness IN ('required','optional','not_applicable')),
    unit_rule TEXT,
    period_rule TEXT,
    mapping_version TEXT NOT NULL,
    UNIQUE (template_name, industry_family, statement_type, canonical_concept, mapping_version)
);

CREATE TABLE IF NOT EXISTS statement_facts (
    statement_fact_id INTEGER PRIMARY KEY,
    fact_id INTEGER NOT NULL UNIQUE REFERENCES xbrl_facts(fact_id) ON DELETE CASCADE,
    ticker TEXT NOT NULL REFERENCES issuers(ticker),
    statement_type TEXT NOT NULL,
    industry_family TEXT NOT NULL,
    institution_type TEXT,
    consolidation_scope TEXT NOT NULL,
    period_role TEXT NOT NULL,
    accumulation TEXT NOT NULL CHECK (accumulation IN ('instant','single_period','year_to_date','annual','unknown')),
    restatement_status TEXT NOT NULL CHECK (restatement_status IN ('as_filed','restated','unknown')),
    concept_mapping_id INTEGER REFERENCES concept_mappings(concept_mapping_id),
    canonical_concept TEXT,
    mapping_status TEXT NOT NULL CHECK (mapping_status IN ('verified','provisional','unknown'))
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id INTEGER PRIMARY KEY,
    fact_id INTEGER REFERENCES xbrl_facts(fact_id) ON DELETE CASCADE,
    statement_fact_id INTEGER REFERENCES statement_facts(statement_fact_id) ON DELETE CASCADE,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error')),
    message TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    UNIQUE (fact_id, statement_fact_id, issue_type, message)
);

CREATE INDEX IF NOT EXISTS idx_raw_documents_ticker_period ON raw_documents(ticker, report_period);
CREATE INDEX IF NOT EXISTS idx_xbrl_facts_concept ON xbrl_facts(concept_id);
CREATE INDEX IF NOT EXISTS idx_statement_facts_filter ON statement_facts(ticker, industry_family, statement_type, period_role);
CREATE INDEX IF NOT EXISTS idx_quality_fact ON data_quality_issues(fact_id);

CREATE VIEW IF NOT EXISTS v_financial_facts AS
SELECT sf.statement_fact_id, sf.ticker, i.company_name, sf.industry_family, sf.institution_type,
       sf.statement_type, sf.consolidation_scope, sf.period_role, sf.accumulation,
       sf.restatement_status, sf.canonical_concept, sf.mapping_status,
       tc.concept_qname, tc.label_zh_tw, tc.label_en,
       xf.raw_value, xf.normalized_value, xf.raw_unit, xf.normalized_unit, xf.decimals,
       xf.value_status, xf.missing_value_reason, rd.report_period, rd.source_url,
       rd.retrieved_at, rd.raw_sha256, xf.fact_sha256
FROM statement_facts sf
JOIN issuers i ON i.ticker = sf.ticker
JOIN xbrl_facts xf ON xf.fact_id = sf.fact_id
JOIN taxonomy_concepts tc ON tc.concept_id = xf.concept_id
JOIN raw_documents rd ON rd.raw_document_id = xf.raw_document_id;

CREATE VIEW IF NOT EXISTS v_general_industrial_financials AS
SELECT * FROM v_financial_facts WHERE industry_family = 'general_industrial';
CREATE VIEW IF NOT EXISTS v_financial_holding_financials AS
SELECT * FROM v_financial_facts WHERE industry_family = 'financial_holding';
CREATE VIEW IF NOT EXISTS v_bank_financials AS
SELECT * FROM v_financial_facts WHERE industry_family = 'bank';
CREATE VIEW IF NOT EXISTS v_insurance_financials AS
SELECT * FROM v_financial_facts WHERE industry_family = 'insurance';
CREATE VIEW IF NOT EXISTS v_securities_financials AS
SELECT * FROM v_financial_facts WHERE industry_family = 'securities';
