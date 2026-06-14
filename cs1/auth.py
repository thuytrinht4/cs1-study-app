"""Streamlit auth helpers built on Supabase email/password.

Single-user convenience: if APP_EMAIL/APP_PASSWORD are set in secrets, the app
auto-signs-in (no login form, survives every redeploy). Otherwise it falls back
to the normal login/sign-up form.
"""
import streamlit as st
from . import db, config


def current_user_id():
    u = st.session_state.get("user")
    return u["id"] if u else None


def _try_autologin():
    """Silently sign in once per session using credentials from secrets."""
    if st.session_state.get("user") or st.session_state.get("autologin_tried"):
        return
    st.session_state["autologin_tried"] = True
    if not config.autologin_ready():
        return
    try:
        res = db.sign_in(config.APP_EMAIL, config.APP_PASSWORD)
        st.session_state["user"] = {"id": res.user.id, "email": res.user.email}
        db.ensure_profile(res.user.id, res.user.email)
    except Exception as e:
        st.session_state["autologin_error"] = str(e)


def ensure_session():
    """Return the user id, auto-logging-in if configured. None if not signed in."""
    if not current_user_id():
        _try_autologin()
    return current_user_id()


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
    uid = ensure_session()
    if not uid:
        st.warning("Please log in on the Home page first.")
        st.stop()
    return uid


def logout_button():
    # With single-user auto-login there's nothing to log out of (it would just
    # sign back in on the next rerun), so hide the button.
    if config.autologin_ready():
        return
    if st.sidebar.button("Log out"):
        db.sign_out()
        st.session_state.pop("user", None)
        st.session_state.pop("autologin_tried", None)
        st.rerun()
