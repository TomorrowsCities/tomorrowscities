from __future__ import annotations

import itertools
from typing import Dict, List

import solara


_counter = itertools.count(1)
notifications = solara.reactive([])  # type: ignore[var-annotated]


def push_notification(level: str, message: str):
    items: List[Dict[str, str]] = list(notifications.value)
    items.append(
        {
            "id": str(next(_counter)),
            "level": level,
            "message": str(message),
        }
    )
    notifications.set(items)


def clear_notifications():
    notifications.set([])


def remove_notification(notification_id: str):
    notifications.set([item for item in notifications.value if item["id"] != notification_id])


def log_info(message: str):
    push_notification("info", message)


def log_warning(message: str):
    push_notification("warning", message)


def log_error(message: str):
    push_notification("error", message)


def log_success(message: str):
    push_notification("success", message)


@solara.component
def NotificationCenter():
    items = notifications.value
    if not items:
        return

    colors = {
        "info": {"background": "#e3f2fd", "border": "#2196f3"},
        "warning": {"background": "#fff9c4", "border": "#fbc02d"},
        "error": {"background": "#ffebee", "border": "#e53935"},
        "success": {"background": "#e8f5e9", "border": "#4caf50"},
    }

    with solara.Column(
        classes=["notification-center"],
        style={
            "position": "fixed",
            "top": "72px",
            "right": "20px",
            "width": "360px",
            "max-width": "calc(100vw - 32px)",
            "max-height": "80vh",
            "overflowY": "auto",
            "zIndex": "9999",
            "gap": "10px",
            "pointerEvents": "auto",
        },
    ):
        with solara.Row(justify="end", style={"width": "100%"}):
            solara.Button("Clear All", on_click=clear_notifications, text=True, outlined=True)

        for item in reversed(items):
            color = colors.get(item["level"], colors["info"])
            with solara.Card(
                elevation=2,
                style={
                    "background": color["background"],
                    "borderLeft": f"5px solid {color['border']}",
                    "width": "100%",
                    "boxSizing": "border-box",
                },
            ):
                with solara.Row(justify="space-between", style={"width": "100%", "alignItems": "flex-start"}):
                    solara.Markdown(f"**{item['level'].upper()}**")
                    solara.Button("Close", on_click=lambda item_id=item["id"]: remove_notification(item_id), text=True)
                solara.Markdown(str(item["message"]))
