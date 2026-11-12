import { Check, Plus, RefreshCw, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { MAX_PEOPLE, MIN_PEOPLE, useFilters } from "../../state/FilterContext";

/** Shown on every comparison page until at least two people are picked.
 * Instead of only saying "select people", it lets the user pick them
 * right here (one click per person) and explains the steps. */
export function SelectPeoplePrompt() {
  const { filters, setFilters, people, selected, peopleLoading, peopleError, refresh } = useFilters();
  const ids = filters.personIds;
  const remaining = Math.max(0, MIN_PEOPLE - ids.length);

  const toggle = (id: string) =>
    setFilters({ personIds: ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id] });

  if (peopleError) {
    return (
      <Shell>
        <h2 className="text-lg font-bold text-navy dark:text-white">Can't reach the backend</h2>
        <p className="mt-1 max-w-lg text-sm text-dark/60 dark:text-silver/60">
          The list of people couldn't be loaded, so nothing can be selected yet. Make sure the
          backend is running -- start the app with <code className="rounded bg-silver/40 px-1">python start_all.py</code> from
          the project folder -- then try again.
        </p>
        <p className="mt-2 text-xs text-dark/40 dark:text-silver/40">Details: {peopleError}</p>
        <button
          type="button"
          onClick={refresh}
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-gold px-4 py-2 text-sm font-bold text-navy-900 shadow-card hover:shadow-card-hover"
        >
          <RefreshCw size={15} /> Try again
        </button>
      </Shell>
    );
  }

  if (peopleLoading) {
    return (
      <Shell>
        <p className="text-sm text-dark/60 dark:text-silver/60">Loading people...</p>
      </Shell>
    );
  }

  if (people.length === 0) {
    return (
      <Shell>
        <h2 className="text-lg font-bold text-navy dark:text-white">No people added yet</h2>
        <p className="mt-1 max-w-lg text-sm text-dark/60 dark:text-silver/60">
          Add the people you want to compare, then scrape or import their Instagram/Facebook data.
        </p>
        <Link
          to="/data-sources"
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-gold px-4 py-2 text-sm font-bold text-navy-900 shadow-card hover:shadow-card-hover"
        >
          <Plus size={15} /> Go to Data Sources
        </Link>
      </Shell>
    );
  }

  return (
    <Shell>
      <h2 className="text-lg font-bold text-navy dark:text-white">Who do you want to compare?</h2>
      <p className="mt-1 max-w-lg text-sm text-dark/60 dark:text-silver/60">
        {remaining > 0
          ? `Pick ${remaining === MIN_PEOPLE ? "at least two people" : "one more person"} below (up to ${MAX_PEOPLE}). You can change the selection any time from the "Comparing" row above.`
          : "Ready."}
      </p>

      <div className="mt-5 flex max-w-3xl flex-wrap justify-center gap-2">
        {people.map((p) => {
          const sel = selected.find((s) => s.id === p.id);
          const full = !sel && ids.length >= MAX_PEOPLE;
          return (
            <button
              key={p.id}
              type="button"
              disabled={full}
              onClick={() => toggle(p.id)}
              className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium shadow-sm transition-all disabled:cursor-not-allowed disabled:opacity-40 ${
                sel
                  ? "text-white"
                  : "border-silver bg-white text-dark hover:-translate-y-0.5 hover:border-navy-300 dark:border-navy-600 dark:bg-navy-800 dark:text-silver"
              }`}
              style={sel ? { backgroundColor: sel.color, borderColor: sel.color } : undefined}
            >
              {sel ? <Check size={14} /> : <Plus size={14} className="text-dark/40" />}
              {p.name}
            </button>
          );
        })}
      </div>

      <ol className="mt-8 grid max-w-3xl grid-cols-1 gap-3 text-left text-xs text-dark/60 sm:grid-cols-3 dark:text-silver/60">
        <Step n={1} title="Pick people">Two or more, each gets their own color on every chart.</Step>
        <Step n={2} title="Set filters">Choose the period, platform and content type above.</Step>
        <Step n={3} title="Explore">Use the sidebar: Overview first, then the Analysis pages.</Step>
      </ol>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-silver bg-white/70 px-6 py-12 text-center dark:border-navy-600 dark:bg-navy-900/60">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-50 text-navy-400 dark:bg-navy-800 dark:text-navy-300">
        <Users size={26} />
      </div>
      {children}
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="rounded-xl border border-silver/60 bg-white p-3 dark:border-navy-700 dark:bg-navy-900">
      <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-dark dark:text-white">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-gold text-[11px] font-bold text-navy-900">{n}</span>
        {title}
      </div>
      {children}
    </li>
  );
}
