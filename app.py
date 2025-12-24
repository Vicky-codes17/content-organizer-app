import re
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st


DATA_FILE = Path("saved_content.csv")
DEFAULT_TAGS = ["Study", "Work", "Idea"]


def load_data() -> pd.DataFrame:
	expected_cols = ["username", "content", "reason", "tags", "saved_on"]
	if DATA_FILE.exists():
		try:
			df = pd.read_csv(DATA_FILE)
		except Exception:
			df = pd.DataFrame(columns=expected_cols)
		# Checks required columns exist
		for c in expected_cols:
			if c not in df.columns:
				df[c] = ""
		# Datetime sorting helper
		if "saved_on" in df.columns:
			# keep original text, but add a helper column for sorting
			try:
				dt = pd.to_datetime(df["saved_on"], errors="coerce")
				df["_saved_on_dt"] = dt
			except Exception:
				df["_saved_on_dt"] = pd.NaT
		return df[expected_cols + (["_saved_on_dt"] if "_saved_on_dt" in df.columns else [])]
	return pd.DataFrame(columns=expected_cols)


def persist_data(df: pd.DataFrame) -> None:
	df.to_csv(DATA_FILE, index=False)


def get_user_data(df: pd.DataFrame, username: str) -> pd.DataFrame:
	"""Filter dataframe to only entries for the given username."""
	return df[df["username"] == username].copy() if not df.empty else df.copy()


def collect_existing_tags(df: pd.DataFrame) -> List[str]:
	tags: List[str] = []
	for cell in df.get("tags", []):
		if isinstance(cell, str) and cell.strip():
			tags.extend([t.strip() for t in cell.split(",") if t.strip()])
	return sorted(set(DEFAULT_TAGS + tags))


def looks_like_url(value: str) -> bool:
	return bool(re.match(r"https?://", value.strip(), flags=re.IGNORECASE))


def init_session_state() -> None:
	"""Initialize session state for user and tag management."""
	if "current_user" not in st.session_state:
		st.session_state.current_user = None
	if "available_tags" not in st.session_state:
		st.session_state.available_tags = DEFAULT_TAGS.copy()
	if "selected_tags" not in st.session_state:
		st.session_state.selected_tags = []
	if "search_active" not in st.session_state:
		st.session_state.search_active = False


st.set_page_config(page_title="Content Organizer (Early Test)", page_icon="file", layout="centered")
st.title("Content Organizer (Early Test)")
st.caption("Save digital content with context so you remember why you saved it, not where it is.")

init_session_state()

# Sidebar login/logout
with st.sidebar:
	st.header("User Account")
	if st.session_state.current_user:
		st.write(f"Logged in as: **{st.session_state.current_user}**")
		if st.button("Logout"):
			st.session_state.current_user = None
			st.session_state.selected_tags = []
			st.rerun()
	else:
		username = st.text_input("Username", placeholder="Enter your username")
		if st.button("Login"):
			if username.strip():
				st.session_state.current_user = username.strip()
				st.rerun()
			else:
				st.warning("Please enter a username.")

# Load all data and filter by current user
all_data = load_data()
if st.session_state.current_user:
	data = get_user_data(all_data, st.session_state.current_user)
	all_tags = collect_existing_tags(data)
	st.session_state.available_tags = all_tags
else:
	data = pd.DataFrame(columns=["username", "content", "reason", "tags", "saved_on"])


with st.container():
	st.header("Save new content")
	if not st.session_state.current_user:
		st.warning("Please log in first to save content.")
	else:
		content_input = st.text_area(
			"Content",
			placeholder="Paste a link or write a short note you'll remember later",
		)
		reason_input = st.text_input(
			"Why did you save this?",
			placeholder="Add the reason or context to help recall it later",
		)

		new_tag = st.text_input("Create a tag", placeholder="e.g., Research")
		if st.button("Add tag"):
			tag_value = new_tag.strip()
			if tag_value and tag_value not in st.session_state.available_tags:
				# Add to available options
				st.session_state.available_tags.append(tag_value)
				st.session_state.available_tags = sorted(set(st.session_state.available_tags))
				# Auto-select it in the multiselect
				if tag_value not in st.session_state.selected_tags:
					st.session_state.selected_tags.append(tag_value)
				st.success(f"Added tag '{tag_value}'.")
			elif tag_value:
				st.warning("That tag already exists.")
			else:
				st.warning("Enter a tag name before adding.")

		st.multiselect(
			"Tags",
			options=st.session_state.available_tags,
			help="Choose tags like study, work, idea.",
			key="selected_tags",
		)

		if st.button("Save", type="primary"):
			if not content_input.strip() or not reason_input.strip():
				st.warning("Please add both content and a reason before saving.")
			else:
				# Merge selected tags with a new tag (if provided)
				effective_tags = list(st.session_state.get("selected_tags", []))
				tag_value = new_tag.strip()
				if tag_value:
					if tag_value not in st.session_state.available_tags:
						st.session_state.available_tags.append(tag_value)
						st.session_state.available_tags = sorted(set(st.session_state.available_tags))
					if tag_value not in effective_tags:
						effective_tags.append(tag_value)

				tags_str = ", ".join(effective_tags) if effective_tags else ""
				new_row = {
					"username": st.session_state.current_user,
					"content": content_input.strip(),
					"reason": reason_input.strip(),
					"tags": tags_str,
					"saved_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
				}
				all_data = pd.concat([all_data, pd.DataFrame([new_row])], ignore_index=True)
				# Recompute helper datetime column for sorting
				try:
					all_data["_saved_on_dt"] = pd.to_datetime(all_data["saved_on"], errors="coerce")
				except Exception:
					all_data["_saved_on_dt"] = pd.NaT
				# Sort by Order
				if "_saved_on_dt" in all_data.columns:
					all_data = all_data.sort_values("_saved_on_dt", ascending=False, kind="stable")
				else:
					all_data = all_data.sort_values("saved_on", ascending=False, kind="stable")
				persist_data(all_data.drop(columns=["_saved_on_dt"], errors="ignore"))
				# Refresh user data
				data = get_user_data(all_data, st.session_state.current_user)
				st.success("Content saved successfully.")


with st.container():
	st.header("Find saved content")
	if not st.session_state.current_user:
		st.warning("Please log in first to view your content.")
	else:
		col1, col2 = st.columns([4, 1])
		with col1:
			search_query = st.text_input("Search your saved items", placeholder="Search by content, reason, or tags")
		with col2:
			if st.button("🔍 Search", key="search_btn"):
				st.session_state.search_active = True
		
		st.subheader("Your saved content")

		if data.empty:
			st.info("Nothing saved yet. Add something above to get started.")
		else:
			filtered = data.copy()
			if st.session_state.search_active and search_query.strip():
				query = search_query.strip().lower()
				mask = (
					filtered["content"].str.lower().str.contains(query, na=False)
					| filtered["reason"].str.lower().str.contains(query, na=False)
					| filtered["tags"].str.lower().str.contains(query, na=False)
				)
				filtered = filtered[mask]

			if st.session_state.search_active and filtered.empty and search_query.strip():
				st.warning("No saved content matches your search.")
			else:
				# Prefer sorting by parsed datetime if available
				if "_saved_on_dt" in filtered.columns:
					filtered = filtered.sort_values("_saved_on_dt", ascending=False)
				else:
					filtered = filtered.sort_values("saved_on", ascending=False)
				table = filtered[["content", "reason", "tags", "saved_on"]].rename(
					columns={
						"content": "Content",
						"reason": "Why saved",
						"tags": "Tags",
						"saved_on": "Saved on",
					},
				)
				# Reset index for better display
				table = table.reset_index(drop=True)
				st.dataframe(table, use_container_width=True)


st.info("This is an early test version. Your honest feedback helps improve the product.")
