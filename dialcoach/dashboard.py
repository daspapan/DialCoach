from __future__ import annotations

import pandas as pd
import streamlit as st

from dialcoach.config import get_settings
from dialcoach.db.repository import Database
from dialcoach.pipeline.scoring import transcript_to_text
from dialcoach.tracker.sync import TrackerSync

st.set_page_config(page_title="Dial Coach", page_icon="\U0001F4DE", layout="wide")


@st.cache_resource
def _settings():
    s = get_settings()
    s.ensure_directories()
    return s


def _load_db() -> Database:
    return Database(_settings().db_path)


def main() -> None:
    st.title("\U0001F4DE Dial Coach")
    st.caption("Local phone-outreach tracker - everything on this page reads from your own machine.")

    settings = _settings()
    if not settings.has_api_key:
        st.warning(
            "ANTHROPIC_API_KEY is not set - call summaries and live coaching are disabled "
            "until you add one to your .env file.",
            icon="⚠️",
        )

    db = _load_db()
    businesses = db.list_businesses()

    tab_pipeline, tab_business, tab_search = st.tabs(["Pipeline", "Business detail", "Search transcripts"])

    with tab_pipeline:
        st.subheader("Pipeline")
        if not businesses:
            st.info("No businesses yet. Run `dialcoach sync-tracker` to pull them from Campaign_Tracker.xlsx.")
        else:
            df = pd.DataFrame(
                [
                    {
                        "Company": b.name,
                        "Contact": b.contact_name,
                        "Status": b.status,
                        "Problem hypothesis": b.problem_hypothesis,
                        "Next step": b.next_step,
                    }
                    for b in businesses
                ]
            )
            counts = df["Status"].value_counts()
            cols = st.columns(len(counts) or 1)
            for col, (status, count) in zip(cols, counts.items()):
                col.metric(status, count)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_business:
        st.subheader("Business detail")
        if not businesses:
            st.info("No businesses yet.")
        else:
            names = [b.name for b in businesses]
            selected_name = st.selectbox("Business", names)
            business = next(b for b in businesses if b.name == selected_name)

            st.write(f"**Industry:** {business.industry or '—'}")
            st.write(f"**Problem hypothesis:** {business.problem_hypothesis or '—'}")
            st.write(f"**Status:** {business.status}  |  **Next step:** {business.next_step or '—'}")
            st.write(f"**Notes:** {business.notes or '—'}")

            calls = db.list_calls_for_business(business.id)
            st.write(f"### Calls ({len(calls)})")
            for call in calls:
                with st.expander(
                    f"Call #{call.id} - {call.started_at} - "
                    f"{(call.temperature or 'unscored').upper()} - {call.status}"
                ):
                    st.write(f"Duration: {call.duration_s or '—'} s  |  Talk ratio (you): "
                             f"{f'{call.talk_ratio:.0%}' if call.talk_ratio is not None else '—'}")
                    st.write(f"Outcome: {call.outcome or '—'}")
                    segments = db.list_segments(call.id)
                    st.code(transcript_to_text(segments) or "(no transcript)", language=None)

                    log_entry = db.get_log_entry_for_call(call.id)
                    if log_entry:
                        st.write(f"**Draft log entry:** {log_entry.summary}")
                        st.write(f"**Draft next step:** {log_entry.next_step}")
                        if not log_entry.confirmed:
                            if st.button(f"Confirm log entry #{log_entry.id}", key=f"confirm-{log_entry.id}"):
                                db.confirm_log_entry(log_entry.id)
                                st.success("Confirmed - run `dialcoach push-log` to sync it to the tracker.")
                        else:
                            st.caption(
                                "Confirmed"
                                + (f", synced {log_entry.synced_at}" if log_entry.synced_at else " - not yet synced")
                            )

    with tab_search:
        st.subheader("Search every transcript")
        query = st.text_input("Search text")
        if query:
            matches = db.search_segments(query)
            st.write(f"{len(matches)} match(es)")
            for m in matches:
                st.write(f"**Call #{m.call_id}** [{m.speaker}] {m.text}")


if __name__ == "__main__":
    main()