import { useEffect, useRef, useState } from "react";

async function api(path, { method = "GET", body } = {}) {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail
          ? JSON.stringify(detail)
          : `HTTP ${response.status}`,
    );
  }
  return data;
}

function cleanName(offer) {
  return offer.name.replace(new RegExp(`^#?${offer.offer_id}\\s*`), "").trim();
}

export default function App() {
  const [view, setView] = useState({ name: "list" });

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => setView({ name: "list" })}>
          <span className="brand-mark">K</span>
          <span>
            Keitaro Wrapper
            <small>campaign builder &amp; offer editor</small>
          </span>
        </button>
      </header>
      {view.name === "list" ? (
        <Home onOpen={(id) => setView({ name: "editor", id })} />
      ) : (
        <Editor id={view.id} onBack={() => setView({ name: "list" })} />
      )}
    </div>
  );
}

function Home({ onOpen }) {
  const [meta, setMeta] = useState(null);
  const [campaigns, setCampaigns] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/campaigns").then(setCampaigns).catch((e) => setError(e.message));
    api("/meta").then(setMeta).catch((e) => setError(e.message));
  }, []);

  return (
    <main className="page">
      <section className="hero">
        <div>
          <h1>Campaigns</h1>
          <p className="muted">
            Create a two-flow campaign: a geo redirect to Google plus an offer
            flow you can edit freely.
          </p>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      <section className="panel">
        <h2>New campaign</h2>
        <Creator meta={meta} onCreated={onOpen} />
      </section>

      <section className="panel">
        <div className="row between">
          <h2>Created campaigns</h2>
          <ImportForm onImported={onOpen} />
        </div>
        {campaigns === null ? (
          <p className="muted">Loading…</p>
        ) : campaigns.length === 0 ? (
          <p className="muted">No campaigns yet. Create one above.</p>
        ) : (
          <div className="table-wrap">
            <table className="list">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Keitaro ID</th>
                  <th>Geo</th>
                  <th>Domain</th>
                  <th>Group</th>
                  <th>Source</th>
                  <th className="num">Offers</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {campaigns.map((campaign) => (
                  <tr key={campaign.id}>
                    <td className="strong">{campaign.name}</td>
                    <td className="mono">{campaign.keitaro_id}</td>
                    <td>{campaign.geo || "—"}</td>
                    <td>{campaign.domain || "—"}</td>
                    <td>{campaign.group || "—"}</td>
                    <td>{campaign.source || "—"}</td>
                    <td className="num">{campaign.offers}</td>
                    <td>
                      {campaign.dirty ? (
                        <span className="chip warn">unpublished</span>
                      ) : (
                        <span className="chip ok">published</span>
                      )}
                    </td>
                    <td className="right">
                      <button className="primary" onClick={() => onOpen(campaign.id)}>
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

function Creator({ meta, onCreated }) {
  const [name, setName] = useState("");
  const [geo, setGeo] = useState("");
  const [offer, setOffer] = useState(null);
  const [domainId, setDomainId] = useState("");
  const [groupId, setGroupId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!meta) return;
    setDomainId(String(meta.domains[0]?.id ?? ""));
    setGroupId(String(meta.groups[0]?.id ?? ""));
    setSourceId(String(meta.sources[0]?.id ?? ""));
  }, [meta]);

  const submit = async (event) => {
    event.preventDefault();
    if (!offer) {
      setError("Pick an offer");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const campaign = await api("/campaigns", {
        method: "POST",
        body: {
          name: name.trim(),
          geo: geo.trim().toUpperCase(),
          offer_id: offer.id,
          domain_id: Number(domainId),
          group_id: Number(groupId),
          traffic_source_id: Number(sourceId),
        },
      });
      onCreated(campaign.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="creator" onSubmit={submit}>
      <label>
        Campaign name
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. flexacil_au_google"
        />
      </label>
      <label>
        Country code
        <input
          required
          className="geo"
          value={geo}
          maxLength={2}
          onChange={(event) => setGeo(event.target.value.toUpperCase())}
          placeholder="AU"
        />
      </label>
      <label className="wide">
        Offer
        <OfferPicker
          value={offer}
          onChange={setOffer}
          placeholder="Search by offer ID or name"
        />
      </label>
      <label>
        Domain
        <select required value={domainId} onChange={(e) => setDomainId(e.target.value)}>
          {meta?.domains.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Group
        <select required value={groupId} onChange={(e) => setGroupId(e.target.value)}>
          {meta?.groups.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Traffic source
        <select required value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
          {meta?.sources.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <div className="actions">
        <button className="primary" disabled={busy || !meta}>
          {busy ? "Creating…" : "Create campaign"}
        </button>
        {error && <span className="error inline">{error}</span>}
      </div>
      <p className="hint">
        Flow 1 accepts {geo.trim() || "the chosen geo"} and redirects to
        https://google.com. Flow 2 sends everyone else to the offer.
      </p>
    </form>
  );
}

function ImportForm({ onImported }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const campaign = await api("/campaigns/import", {
        method: "POST",
        body: { keitaro_id: Number(value) },
      });
      onImported(campaign.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="import" onSubmit={submit}>
      <input
        required
        type="number"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Keitaro ID"
        title="Import an existing Keitaro campaign by ID"
      />
      <button disabled={busy || !value}>Import</button>
      {error && <span className="error inline">{error}</span>}
    </form>
  );
}

function OfferPicker({ value, onChange, placeholder }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const root = useRef(null);

  useEffect(() => {
    const close = (event) => {
      if (root.current && !root.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const timer = setTimeout(
      async () => {
        setLoading(true);
        try {
          const found = await api(`/offers?q=${encodeURIComponent(query.trim())}`);
          if (!cancelled) setResults(found);
        } catch {
          if (!cancelled) setResults([]);
        } finally {
          if (!cancelled) setLoading(false);
        }
      },
      query.trim() ? 250 : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, open]);

  if (value) {
    return (
      <div className="picked">
        <span className="picked-text">
          <b className="mono">#{value.id}</b> {value.name}
        </span>
        <button type="button" className="ghost" onClick={() => onChange(null)}>
          Change
        </button>
      </div>
    );
  }

  return (
    <div className="picker" ref={root}>
      <input
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
      />
      {open && (
        <div className="dropdown">
          {loading ? (
            <div className="muted small">Searching…</div>
          ) : results.length === 0 ? (
            <div className="muted small">Nothing found</div>
          ) : (
            results.map((offer) => (
              <button
                type="button"
                key={offer.id}
                onClick={() => {
                  onChange(offer);
                  setOpen(false);
                  setQuery("");
                }}
              >
                <b className="mono">#{offer.id}</b>
                <span>{cleanName(offer)}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function Editor({ id, onBack }) {
  const [campaign, setCampaign] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/campaigns/${id}`).then(setCampaign).catch((e) => setError(e.message));
  }, [id]);

  const fetchStreams = async () => {
    setBusy(true);
    setError("");
    try {
      setCampaign(await api(`/campaigns/${id}/fetch`, { method: "POST" }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const changeStream = (stream) =>
    setCampaign((current) => ({
      ...current,
      streams: current.streams.map((item) => (item.id === stream.id ? stream : item)),
    }));

  if (!campaign) {
    return (
      <main className="page">
        {error ? <div className="error">{error}</div> : <p className="muted">Loading…</p>}
      </main>
    );
  }

  return (
    <main className="page">
      <button className="back" onClick={onBack}>
        ← All campaigns
      </button>

      <section className="hero campaign-head">
        <div>
          <h1>{campaign.name}</h1>
          <p className="muted">
            Keitaro #{campaign.keitaro_id}
            {campaign.geo && ` · ${campaign.geo}`}
            {campaign.domain && ` · ${campaign.domain}`}
            {campaign.group && ` · ${campaign.group}`}
            {campaign.source && ` · ${campaign.source}`}
          </p>
        </div>
        <button onClick={fetchStreams} disabled={busy}>
          {busy ? "Fetching…" : "Fetch streams"}
        </button>
      </section>

      {error && <div className="error">{error}</div>}

      <div className="flows">
        {campaign.streams.map((stream) => (
          <StreamCard key={stream.id} stream={stream} onChange={changeStream} />
        ))}
      </div>
    </main>
  );
}

function StreamCard({ stream, onChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const act = async (path, method = "POST", body) => {
    setBusy(true);
    setError("");
    try {
      onChange(await api(path, { method, body }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!stream.editable) {
    return (
      <section className="flow plain">
        <div className="flow-head">
          <span className="pos">{stream.position}</span>
          <h2>Flow {stream.position}</h2>
          <span className="flow-name">{stream.name}</span>
          <span className="chip">redirect flow</span>
        </div>
        <p className="muted small">
          No offers in this flow — it is shown as-is and is not managed by the
          editor.
        </p>
      </section>
    );
  }

  return (
    <section className="flow">
      <div className="flow-head">
        <span className="pos">{stream.position}</span>
        <h2>Flow {stream.position}</h2>
        <span className="flow-name">{stream.name}</span>
        {stream.dirty && <span className="chip warn">unpublished changes</span>}
        <span className="spacer" />
        {stream.dirty && (
          <>
            <button disabled={busy} onClick={() => act(`/streams/${stream.id}/cancel`)}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={busy}
              onClick={() => act(`/streams/${stream.id}/push`)}
            >
              {busy ? "Working…" : "Push"}
            </button>
          </>
        )}
      </div>

      {error && <div className="error">{error}</div>}

      <div className={`table-wrap offers-wrap ${stream.dirty ? "dirty" : ""}`}>
        <table className="offers">
          <thead>
            <tr>
              <th>Offer</th>
              <th className="num share-col">Share</th>
              <th className="pin-col">Pin</th>
              <th className="right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {stream.offers.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  No offers yet — add one below.
                </td>
              </tr>
            )}
            {stream.offers.map((offer) => (
              <OfferRow
                key={offer.offer_id}
                offer={offer}
                busy={busy}
                onPin={() =>
                  act(`/streams/${stream.id}/offers/${offer.offer_id}/pin`, "POST", {
                    pinned: !offer.pinned,
                  })
                }
                onRemove={() =>
                  act(`/streams/${stream.id}/offers/${offer.offer_id}`, "DELETE")
                }
                onRestore={() =>
                  act(`/streams/${stream.id}/offers/${offer.offer_id}/restore`)
                }
              />
            ))}
          </tbody>
        </table>
      </div>

      <AddOffer streamId={stream.id} onChanged={onChange} />
    </section>
  );
}

function OfferRow({ offer, busy, onPin, onRemove, onRestore }) {
  return (
    <tr className={offer.removed ? "removed" : ""}>
      <td>
        <b className="mono">#{offer.offer_id}</b>{" "}
        <span className="offer-name">{cleanName(offer)}</span>
        {offer.removed && <span className="removed-mark">(removed)</span>}
      </td>
      <td className="num share-col">{offer.share}%</td>
      <td className="pin-col">
        {!offer.removed && (
          <button
            className={`pin ${offer.pinned ? "on" : ""}`}
            disabled={busy}
            title={offer.pinned ? "Unpin share" : "Pin share"}
            onClick={onPin}
          >
            {offer.pinned ? "Pinned" : "Pin"}
          </button>
        )}
      </td>
      <td className="right">
        {offer.removed ? (
          <button disabled={busy} onClick={onRestore}>
            Bring back
          </button>
        ) : (
          <button className="danger" disabled={busy} onClick={onRemove}>
            Remove
          </button>
        )}
      </td>
    </tr>
  );
}

function AddOffer({ streamId, onChanged }) {
  const [offer, setOffer] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const add = async () => {
    if (!offer) return;
    setBusy(true);
    setError("");
    try {
      onChanged(
        await api(`/streams/${streamId}/offers`, {
          method: "POST",
          body: { offer_id: offer.id },
        }),
      );
      setOffer(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="add-offer">
      <OfferPicker
        value={offer}
        onChange={setOffer}
        placeholder="Add offer — search by ID or name"
      />
      <button className="primary" disabled={!offer || busy} onClick={add}>
        Add
      </button>
      {error && <span className="error inline">{error}</span>}
    </div>
  );
}
