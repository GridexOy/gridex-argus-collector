"""tkinter widgets of the Jono and Lahetys blocks; render props only."""

from __future__ import annotations

from tkinter import ttk

from argus_collector.ui.queue_lines import DeliveryProps, QueueProps

COLOURS = {"ok": "#1a7f37", "warn": "#9a6700", "error": "#b42318", "info": "#57606a"}
FG = "#1f2328"
COLUMN_WIDTHS = (190, 130, 70, 70, 70, 360)
QUEUE_ROWS = 6
PAD_X = 12
PAD_Y = 4


class QueueBlock:
    """Jono: a state line (Ladataan / lataus epaonnistui / Ei tehtavia) or the table."""

    def __init__(self, parent: ttk.Frame, props: QueueProps) -> None:
        self.state_label = ttk.Label(parent, text="")
        self.state_label.pack(anchor="w", padx=PAD_X)
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=PAD_X, pady=PAD_Y)
        ids = [f"q{i}" for i in range(len(props.columns))]
        self.table = ttk.Treeview(frame, columns=ids, show="headings", height=QUEUE_ROWS)
        for column, heading, width in zip(ids, props.columns, COLUMN_WIDTHS, strict=False):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor="w")
        for level, colour in COLOURS.items():
            self.table.tag_configure(level, foreground=colour)
        self.table.pack(side="left", fill="x", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")
        self.render(props)

    def render(self, props: QueueProps) -> None:
        self.state_label.configure(
            text=props.state_text, foreground=COLOURS.get(props.state_level, FG)
        )
        self.table.delete(*self.table.get_children())
        for row, level in zip(props.rows, props.row_levels, strict=False):
            self.table.insert("", "end", values=row, tags=(level,))

    def rows(self) -> list[tuple[str, ...]]:
        return [tuple(self.table.item(i, "values")) for i in self.table.get_children()]


class DeliveryBlock:
    """Lahetys: pending / errors / p95 and the transport state."""

    def __init__(self, parent: ttk.Frame, props: DeliveryProps) -> None:
        self.counts_label = ttk.Label(parent, text="")
        self.counts_label.pack(anchor="w", padx=PAD_X)
        self.state_label = ttk.Label(parent, text="")
        self.state_label.pack(anchor="w", padx=PAD_X)
        self.render(props)

    def render(self, props: DeliveryProps) -> None:
        self.counts_label.configure(
            text=props.counts_text, foreground=COLOURS.get(props.counts_level, FG)
        )
        self.state_label.configure(
            text=props.state_text, foreground=COLOURS.get(props.state_level, FG)
        )
