import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Search, ArrowUpRight, ArrowLeft, Layers3, Activity, BookOpen,
  GitCompareArrows, ArrowRight, Check, Command, SlidersHorizontal
} from 'lucide-react';
import './style.css';

type Mode = 'bm25' | 'dense' | 'hybrid' | 'ltr';
type View = 'search' | 'compare' | 'evaluation' | 'about';

type Hit = { id: string; title: string; excerpt: string; score: number; mode: Mode };

type Response = { query: string; mode: Mode; results: Hit[]; server_ms: number };

type Status = {
  ready: boolean;
  available_modes: Mode[];
  documents: number;
  message: string | null;
  bundle_version: string;
  metadata: {
    model: string;
    revision: string;
    provenance: { profile: string; license: string };
    ranker?: unknown;
  } | null;
};

type Report = {
  profile: string;
  split: string;
  queries: number;
  documents: number;
  metrics: Record<Mode, { aggregate: Record<string, number> }>;
};

type Document = {
  id: string;
  title: string;
  text: string;
  attribution: { license: string; source: string };
};

const EXCERPT_LIMIT = 450;
const QUERY_LIMIT = 500;

const modes: {
  id: Mode; title: string; description: string; tag: string; explanation: string;
}[] = [
  {
    id: 'bm25', title: 'Keyword', tag: 'BM25',
    description: 'Find the words that matter.',
    explanation: 'BM25 matches query terms to source documents, accounting for term frequency and document length.'
  },
  {
    id: 'dense', title: 'Semantic', tag: 'DENSE',
    description: 'Search beyond exact words.',
    explanation: 'A Sentence Transformer embeds questions and documents. Exact cosine search finds nearby meanings.'
  },
  {
    id: 'hybrid', title: 'Hybrid', tag: 'RRF',
    description: 'Bring both perspectives together.',
    explanation: 'Reciprocal rank fusion combines the first 100 results from each retriever using a fixed constant of 60.'
  },
  {
    id: 'ltr', title: 'Learned ranking', tag: 'XGBOOST',
    description: 'Reorder with a trained model.',
    explanation: 'An XGBoost ranker learns from training relevance judgments using seven shared retrieval features.'
  }
];

const navigation: { id: View; label: string; Icon: typeof Search }[] = [
  { id: 'search', label: 'Search explorer', Icon: Search },
  { id: 'compare', label: 'Compare modes', Icon: GitCompareArrows },
  { id: 'evaluation', label: 'Benchmark result', Icon: Activity },
  { id: 'about', label: 'About the project', Icon: BookOpen }
];

const viewTitles: Record<View, string> = {
  search: 'Search explorer',
  compare: 'Compare modes',
  evaluation: 'Benchmark result',
  about: 'About'
};

const examples = {
  fixture: ['How does savings interest compound?', 'What is a diversified index fund?'],
  fiqa: ['Income tax exemptions for small business?', 'Do I need a business credit card?']
};

async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === 'string'
        ? body.detail
        : 'The request could not be completed. Please try again.'
    );
  }
  return r.json();
}

function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [view, setView] = useState<View>('search');
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<Mode>('hybrid');
  const [result, setResult] = useState<Response | null>(null);
  const [comparisons, setComparisons] = useState<Response[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [reports, setReports] = useState<Report[]>([]);
  const [doc, setDoc] = useState<Document | null>(null);

  const request = useRef<AbortController | null>(null);
  const queryRef = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const lastLink = useRef<string | null>(null);

  const isFixture = status?.metadata?.provenance.profile === 'fixture';

  useEffect(() => {
    get<Status>('/api/status')
      .then(s => {
        setStatus(s);
        if (!s.ready) setError(s.message || 'Search is unavailable.');
      })
      .catch(e => setError(e.message));
    return () => request.current?.abort();
  }, []);

  async function route() {
    const id = new URLSearchParams(location.search).get('doc');
    if (!id) {
      setDoc(null);
      return;
    }
    try {
      const d = await get<Document>('/api/documents/' + encodeURIComponent(id));
      // Ignore a response for a document the user has already navigated away from.
      if (new URLSearchParams(location.search).get('doc') === id) setDoc(d);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // Move focus into the document, and back to its originating link on return.
  useEffect(() => {
    if (doc) heading.current?.focus();
    else if (lastLink.current) document.getElementById(lastLink.current)?.focus();
  }, [doc]);

  useEffect(() => {
    route();
    window.addEventListener('popstate', route);
    return () => window.removeEventListener('popstate', route);
  }, []);

  async function search(q = query, m = mode, compare = view === 'compare') {
    if (!q.trim()) {
      queryRef.current?.focus();
      return;
    }
    // Abort any in-flight request so a slow response cannot replace a newer one.
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;

    setBusy(true);
    setError('');
    setQuery(q);
    setDoc(null);

    try {
      if (compare) {
        const all: Response[] = [];
        const available = modes.filter(x => status?.available_modes.includes(x.id));
        for (const method of available) {
          const params = new URLSearchParams({ q, mode: method.id, k: '5' });
          all.push(await get<Response>('/api/search?' + params, controller.signal));
        }
        if (!controller.signal.aborted) setComparisons(all);
      } else {
        const params = new URLSearchParams({ q, mode: m, k: '10' });
        const r = await get<Response>('/api/search?' + params, controller.signal);
        if (!controller.signal.aborted) setResult(r);
      }
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  function navigate(v: View) {
    request.current?.abort();
    setBusy(false);
    setError('');
    setDoc(null);
    setView(v);
    history.replaceState({}, '', location.pathname);
    if (v === 'evaluation') {
      get<{ reports: Report[] }>('/api/evaluation')
        .then(r => setReports(r.reports))
        .catch(e => setError(e.message));
    }
  }

  function openDoc(e: React.MouseEvent, hit: Hit, elementId: string) {
    // Let the browser handle modified clicks (new tab, new window).
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    lastLink.current = elementId;
    history.pushState({}, '', '?doc=' + encodeURIComponent(hit.id));
    route();
  }

  function goBack() {
    if (lastLink.current) {
      history.back();
    } else {
      history.replaceState({}, '', location.pathname);
      route();
    }
  }

  function statusMessage() {
    if (busy) return 'Searching the collection…';
    if (result && view === 'search') {
      return `${result.results.length} results · ${result.server_ms} ms server processing time`;
    }
    if (comparisons.length && view === 'compare') return 'Comparison complete';
    return '';
  }

  function hitCard(hit: Hit, index: number, prefix: string) {
    const id = prefix + '-' + hit.id;
    return (
      <article className="result" key={hit.id}>
        <span className="rank">{String(index + 1).padStart(2, '0')}</span>
        <div className="result-body">
          <div className="eyebrow source">
            <BookOpen size={13} /> {isFixture ? 'FIXTURE COLLECTION' : 'FIQA COLLECTION'}
            <span> / {hit.id}</span>
          </div>
          <h3>
            <a
              id={id}
              href={'?doc=' + encodeURIComponent(hit.id)}
              onClick={e => openDoc(e, hit, id)}
            >
              {hit.title}
              <ArrowUpRight size={17} />
            </a>
          </h3>
          <p>{hit.excerpt}{hit.excerpt.length >= EXCERPT_LIMIT ? '…' : ''}</p>
          <div className="score">
            <span>{modes.find(m => m.id === hit.mode)?.tag}</span> Retrieval score{' '}
            <strong>{hit.score.toFixed(4)}</strong>
          </div>
        </div>
      </article>
    );
  }

  function renderSidebar() {
    return (
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="RankForge home">
          <span className="brand-icon"><Layers3 size={23} /></span>
          {' '}RankForge<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">SEARCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => navigate(id)}
              aria-current={view === id ? 'page' : undefined}
              className={view === id ? 'nav-item active' : 'nav-item'}
            >
              <Icon size={18} />
              <span>{label}</span>
              {view === id && <span className="nav-indicator" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div className="small-label">BUILT TO BE EXPLORED</div>
          <p>One collection.<br />Four ways to find meaning.</p>
          <div className="mini-lines"><i /><i /><i /><i /><i /></div>
        </div>
        <div className="sidebar-bottom">
          <span className={'dot ' + (status?.ready ? 'online' : '')} />
          {status?.ready ? 'Search engine ready' : 'Engine unavailable'}
          <span className="version">v1.0</span>
        </div>
      </aside>
    );
  }

  function renderDocument(open: Document) {
    return (
      <section className="document-view">
        <button className="text-button" onClick={goBack}>
          <ArrowLeft size={16} /> Back to results
        </button>
        <div className="eyebrow">SOURCE DOCUMENT / {open.id}</div>
        <h1 ref={heading} tabIndex={-1}>{open.title}</h1>
        <p className="document-text">{open.text}</p>
        <footer>
          Archived source text · {open.attribution.license}.{' '}
          <a href="https://huggingface.co/datasets/BeIR/fiqa">Dataset attribution</a>
        </footer>
      </section>
    );
  }

  function renderSearchPanel() {
    return (
      <section className="search-panel" aria-label="Search controls">
        <form onSubmit={e => { e.preventDefault(); search(); }}>
          <label htmlFor="query">What would you like to explore?</label>
          <div className="query-box">
            <Search size={22} />
            <input
              id="query"
              ref={queryRef}
              placeholder="Ask a question about finance…"
              value={query}
              maxLength={QUERY_LIMIT}
              onChange={e => setQuery(e.target.value)}
            />
            <button className="search-button" disabled={!status?.ready} type="submit">
              Search <ArrowRight size={17} />
            </button>
          </div>
          <fieldset>
            <legend><SlidersHorizontal size={13} /> RETRIEVAL METHOD</legend>
            <div className="mode-grid">
              {modes.map(m => {
                const unavailable = !status?.available_modes.includes(m.id);
                return (
                  <label
                    className={'mode-card ' + (mode === m.id ? 'selected' : '')}
                    key={m.id}
                  >
                    <input
                      type="radio"
                      name="mode"
                      value={m.id}
                      checked={mode === m.id}
                      disabled={unavailable}
                      onChange={() => {
                        setMode(m.id);
                        if (result && view === 'search') search(query, m.id, false);
                      }}
                    />
                    <span className="mode-title">
                      {m.title}{mode === m.id && <Check size={15} />}
                    </span>
                    <span className="mode-description">
                      {status && unavailable ? 'Model unavailable' : m.description}
                    </span>
                    <span className="mode-tag">{m.tag}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        </form>
        <div className="examples">
          <span>TRY A QUERY</span>
          {(isFixture ? examples.fixture : examples.fiqa).map(q => (
            <button key={q} onClick={() => search(q)}>
              {q}<ArrowUpRight size={12} />
            </button>
          ))}
        </div>
      </section>
    );
  }

  function renderIntro() {
    return (
      <div className="intro-grid">
        <div className="intro-illustration" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <span className="orbit-center"><Layers3 size={28} /></span>
          <span className="orbit-chip chip-a">keyword</span>
          <span className="orbit-chip chip-b">meaning</span>
          <span className="orbit-chip chip-c">relevance</span>
        </div>
        <div className="intro-copy">
          <span className="eyebrow">MORE THAN A MATCH</span>
          <h2>See how search thinks.</h2>
          <p>
            Follow a query from exact words to semantic meaning. Switch methods,
            inspect the source, and see what changes.
          </p>
          <button className="text-button" onClick={() => navigate('about')}>
            Explore the approach <ArrowRight size={16} />
          </button>
        </div>
        <div className="collection-stat">
          <span className="eyebrow">THE COLLECTION</span>
          <strong>{status?.documents.toLocaleString() || '—'}</strong>
          <span>source documents</span>
          <hr />
          <p>
            {isFixture
              ? 'Hand-authored fixture data for development and correctness checks.'
              : 'Archived financial Q&A from the BEIR FiQA-2018 dataset.'}
          </p>
        </div>
      </div>
    );
  }

  function renderResults() {
    if (view === 'compare' && comparisons.length > 0) {
      return (
        <div className="comparison-grid">
          {comparisons.map(r => (
            <section key={r.mode}>
              <h2>{modes.find(m => m.id === r.mode)?.title}</h2>
              <small>{r.server_ms} ms server processing time</small>
              {r.results.map((h, i) => hitCard(h, i, r.mode))}
            </section>
          ))}
        </div>
      );
    }
    if (view === 'search' && result) {
      return (
        <div className={'results ' + (busy ? 'loading' : '')}>
          {result.results.length ? (
            result.results.map((h, i) => hitCard(h, i, 'result'))
          ) : (
            <div className="empty">
              <Search />
              <h3>No matching documents</h3>
              <p>Try different words or another retrieval method.</p>
            </div>
          )}
        </div>
      );
    }
    return renderIntro();
  }

  function renderSearchView() {
    const comparing = view === 'compare';
    return (
      <>
        <div className="page-heading">
          <div>
            <div className="eyebrow"><span className="tiny-line" /> THE RETRIEVAL LAB</div>
            <h1>
              {comparing
                ? 'A different lens on every query.'
                : 'Good answers start with better search.'}
            </h1>
            <p>
              {comparing
                ? 'Compare how four retrieval methods order the same collection.'
                : 'Explore financial knowledge through keywords, meaning, and learned relevance.'}
            </p>
          </div>
          <span className="edition">01 / EXPLORE</span>
        </div>
        {renderSearchPanel()}
        {error && <div role="alert" className="error">{error}</div>}
        <div className="result-heading">
          <h2>
            {comparing
              ? 'Side-by-side results'
              : result
                ? 'Search results'
                : 'Your next discovery starts here'}
          </h2>
          <span role="status" aria-live="polite">{statusMessage()}</span>
        </div>
        {renderResults()}
        <p className="fine-print">
          Original source excerpts. Scores indicate retrieval relevance, not
          confidence or financial advice.
        </p>
      </>
    );
  }

  function renderReport(r: Report) {
    return (
      <section className="evaluation-card" key={r.split}>
        <div className="evaluation-heading">
          <h2>{r.profile} · {r.split} split</h2>
          <span>{r.queries} queries / {r.documents.toLocaleString()} documents</span>
        </div>
        <div className="table-scroll">
          <table>
            <caption>
              Retrieval quality; higher is better. Fixture results are correctness
              checks, not benchmark claims.
            </caption>
            <thead>
              <tr>
                <th>Method</th><th>nDCG@10</th><th>MRR@10</th><th>Recall@100</th>
              </tr>
            </thead>
            <tbody>
              {modes.map(m => r.metrics[m.id] && (
                <tr key={m.id}>
                  <th scope="row">{m.title}</th>
                  {['nDCG@10', 'RR@10', 'R@100'].map(metric => (
                    <td key={metric}>
                      {(r.metrics[m.id].aggregate[metric] ?? 0).toFixed(4)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  function renderEvaluationView() {
    return (
      <>
        <div className="eyebrow">MEASURED, NOT ASSUMED</div>
        <h1>Benchmark result</h1>
        <p className="lede">
          Saved results averaged across predefined development and test queries.
          For your current query’s rankings, use Search explorer or Compare modes.
        </p>
        {error && <p role="alert">{error}</p>}
        {!reports.length ? (
          <section className="empty">
            <Activity />
            <h2>No matching benchmark report</h2>
            <p>
              Measured results will appear when a report for this artifact bundle
              is available.
            </p>
          </section>
        ) : (
          reports.map(renderReport)
        )}
        <p className="fine-print">
          The learned ranker reorders the same 100 hybrid candidates, so it cannot
          increase Recall@100. Unjudged documents count as nonrelevant; judgments
          may be incomplete.
        </p>
      </>
    );
  }

  function renderAboutView() {
    return (
      <>
        <div className="eyebrow">ABOUT RANKFORGE</div>
        <h1>Search, understood.</h1>
        <p className="lede">
          A small, inspectable platform for comparing information retrieval approaches.
        </p>
        <div className="about-grid">
          {modes.map((m, i) => (
            <section key={m.id}>
              <span className="eyebrow">0{i + 1} / {m.tag}</span>
              <h2>{m.title}</h2>
              <p>{m.explanation}</p>
            </section>
          ))}
        </div>
        <section className="technical">
          <h2>Collection &amp; model</h2>
          <dl>
            <dt>Profile</dt>
            <dd>{status?.metadata?.provenance.profile}</dd>
            <dt>Embedding model</dt>
            <dd>{status?.metadata?.model}</dd>
            <dt>Dataset license</dt>
            <dd>{status?.metadata?.provenance.license}</dd>
            <dt>Artifact version</dt>
            <dd>{status?.bundle_version?.slice(0, 16)}</dd>
          </dl>
          <p>
            One original document per retrieval unit. Missing titles remain labeled
            with source IDs. This application retrieves archived text; it does not
            generate answers.
          </p>
          <a href="https://huggingface.co/datasets/BeIR/fiqa">
            FiQA dataset &amp; attribution <ArrowUpRight size={14} />
          </a>
        </section>
      </>
    );
  }

  function renderMain() {
    if (doc) return renderDocument(doc);
    if (view === 'search' || view === 'compare') return renderSearchView();
    if (view === 'evaluation') return renderEvaluationView();
    return renderAboutView();
  }

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      {renderSidebar()}
      <div className="workspace">
        <header className="topbar">
          <span>
            Workspace <span className="slash">/</span>{' '}
            <strong>{doc ? 'Source document' : viewTitles[view]}</strong>
          </span>
          <span className="collection-badge">
            <span className="dot online" />
            {isFixture ? 'Fixture corpus' : 'FiQA collection'}
          </span>
        </header>
        <main id="main">{renderMain()}</main>
        <footer className="page-footer">
          <span>
            RankForge <span className="footer-separator">/</span> A closer look at relevance.
          </span>
          <span><Command size={12} /> Built for exploration</span>
        </footer>
      </div>
    </>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
