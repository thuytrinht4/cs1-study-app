"""Streamlit auth helpers built on Supabase email/password."""
import streamlit as st
from . import db


def current_user_id():
    u = st.session_state.get("user")
    return u["id"] if u else None


def login_form():
    """Render a login / sign-up form. Sets st.session_state['user'] on success."""
    st.subheader("Sign in")
    tab_in, tab_up = st.tabs(["Log in", "Create account"])

    with tab_in:
        with st.form("login"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                try:
                    res = db.sign_in(email, pw)
                    st.session_state["user"] = {"id": res.user.id, "email": res.user.email}
                    db.ensure_profile(res.user.id, email)
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with tab_up:
        with st.form("signup"):
            email2 = st.text_input("Email", key="su_email")
            pw2 = st.text_input("Password (min 6 chars)", type="password", key="su_pw")
            if st.form_submit_button("Create account"):
                try:
                    res = db.sign_up(email2, pw2)
                    if res.user:
                        st.success("Account created. If email confirmation is on, "
                                   "confirm via email, then log in. Otherwise just log in.")
                    else:
                        st.info("Check your email to confirm, then log in.")
                except Exception as e:
                    st.error(f"Sign-up failed: {e}")


def require_login():
    """Call at the top of every page. Returns the user id or stops the page."""
    uid = current_user_id()
    if not uid:
        st.warning("Please log in on the Home page first.")
        st.stop()
    return uid


def logout_button():
    if st.sidebar.button("Log out"):
        db.sign_out()
        st.session_state.pop("user", None)
        st.rerun()
