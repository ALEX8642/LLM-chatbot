"""Table store: every table row in SQLite, found exactly by `lookup_table`.

General for any manual, not a parts-list special case:

- **Header rows:** parser-flagged header cells if any; otherwise the leading rows before
  the first data row (a row with at least two non-empty cells containing a digit that is
  not a column number in parentheses, like "(3)").
- **Group label:** in a sparse non-data row (at most half the columns filled; header
  rows are full), the longest cell of 20 or more characters. It applies to the
  following rows, and to following pages of the same manual, until the next group label.
  ``figure`` is the number after FIG/FIGURE in the group label, if any. Cells starting
  with a column number ("(7) USMC QTY") are header labels, never group labels. A text
  line inside the table that names a figure also sets the group for the rows below it,
  because the parser's table HTML can drop such lines.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from rapidfuzz import fuzz

from manualqa.blocks import Block, PageParse
from manualqa.geometry import Box
from manualqa.table_geometry import row_boxes
from manualqa.textnorm import norm

GROUP_MIN_CHARS = 20
HEADER_MATCH_MIN = 80
_COLUMN_NUMBER = re.compile(r"^\(\d+\)")
_FIGURE = re.compile(r"\bFIG(?:URE)?\.?\s*(\d+[A-Z]?)", re.I)


@dataclass
class TableInfo:
    header: list[str]
    header_rows: int
    groups: dict[int, str]


@dataclass
class RowHit:
    table_id: str
    manual: str
    page: int
    block_id: str
    row: int
    header: list[str]
    cells: list[str]
    cell_boxes: list[Box | None]
    row_box: Box | None
    group: str | None
    figure: str | None


def _grid(block: Block) -> tuple[int, dict[int, dict[int, str]]]:
    width = max((c.col for c in block.cells), default=-1) + 1
    rows: dict[int, dict[int, str]] = {}
    for c in block.cells:
        rows.setdefault(c.row, {})[c.col] = c.text
    return width, rows


def _is_data_row(texts: list[str]) -> bool:
    numeric = [t for t in texts if t.strip() and any(ch.isdigit() for ch in t)]
    return len([t for t in numeric if not _COLUMN_NUMBER.match(t.strip())]) >= 2


def _group_in(texts: list[str]) -> str | None:
    """The longest cell of 20+ characters that is not a numbered column label."""
    long = [
        t.strip()
        for t in texts
        if len(t.strip()) >= GROUP_MIN_CHARS and not _COLUMN_NUMBER.match(t.strip())
    ]
    return max(long, key=len) if long else None


def _figure(group: str | None) -> str | None:
    match = _FIGURE.search(group) if group else None
    return match.group(1) if match else None


def derive_table(block: Block) -> TableInfo:
    width, rows = _grid(block)
    order = sorted(rows)
    flagged = {c.row for c in block.cells if c.header}
    if flagged:
        header_rows = [r for r in order if r in flagged]
    else:
        header_rows = []
        for r in order:
            if _is_data_row(list(rows[r].values())):
                break
            header_rows.append(r)
    groups: dict[int, str] = {}
    for r in order:
        texts = list(rows[r].values())
        filled = sum(1 for t in texts if t.strip())
        if not _is_data_row(texts) and filled <= max(1, width) / 2:
            group = _group_in(texts)
            if group:
                groups[r] = group
    header = []
    for col in range(width):
        parts = [
            rows[r].get(col, "").strip()
            for r in header_rows
            if rows[r].get(col, "").strip() != groups.get(r)
        ]
        header.append(" ".join(p for p in parts if p))
    return TableInfo(header=header, header_rows=len(header_rows), groups=groups)


def _box_json(box: Box | None) -> str | None:
    return None if box is None else json.dumps(asdict(box))


def _box(text: str | None) -> Box | None:
    return None if text is None else Box(**json.loads(text))


class TableStore:
    def __init__(self, path: Path | str) -> None:
        # the server reads from worker threads; writes happen once, at ingestion
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tables (
                table_id TEXT PRIMARY KEY, manual TEXT, page INTEGER, block_id TEXT,
                header TEXT, box TEXT);
            CREATE TABLE IF NOT EXISTS rows (
                id INTEGER PRIMARY KEY, table_id TEXT, row INTEGER, cells TEXT,
                cell_boxes TEXT, row_box TEXT, grp TEXT, figure TEXT, manual TEXT);
            CREATE VIRTUAL TABLE IF NOT EXISTS rows_fts USING fts5(
                text, tokenize="unicode61 tokenchars '-.'");
            """)
        self._group: dict[str, str | None] = {}

    def add_page(self, pp: PageParse) -> None:
        """Add a page's tables. Pages of a manual must be added in page order."""
        for block in pp.blocks:
            if block.kind != "table" or not block.cells:
                continue
            info = derive_table(block)
            width, grid = _grid(block)
            boxes = {(c.row, c.col): c.box for c in block.cells}
            rbox = row_boxes(block)
            self.db.execute(
                "INSERT OR REPLACE INTO tables VALUES (?,?,?,?,?,?)",
                (
                    block.id,
                    pp.manual,
                    pp.page,
                    block.id,
                    json.dumps(info.header),
                    _box_json(block.box),
                ),
            )
            group = self._group.get(pp.manual)
            # figure lines in the table region (the parser's HTML can drop them)
            marks = sorted(
                (ln.box.center[1], ln.text.strip())
                for ln in block.lines
                if _FIGURE.search(ln.text)
            )
            for i, r in enumerate(sorted(grid)):
                if r in info.groups:
                    group = info.groups[r]
                if r in rbox:
                    above = [text for y, text in marks if y < rbox[r].y0]
                    if above and _figure(above[-1]) != _figure(group):
                        group = above[-1]
                cells = [grid[r].get(col, "") for col in range(width)]
                if i < info.header_rows or not _is_data_row(cells):
                    continue
                figure = _figure(group)
                cur = self.db.execute(
                    "INSERT INTO rows (table_id,row,cells,cell_boxes,row_box,grp,figure,"
                    "manual) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        block.id,
                        r,
                        json.dumps(cells),
                        json.dumps(
                            [_box_json(boxes.get((r, col))) for col in range(width)]
                        ),
                        _box_json(rbox.get(r)),
                        group,
                        figure,
                        pp.manual,
                    ),
                )
                text = " ".join(cells + [group or ""])
                self.db.execute(
                    "INSERT INTO rows_fts (rowid, text) VALUES (?, ?)",
                    (cur.lastrowid, text),
                )
            self._group[pp.manual] = group
        self.db.commit()

    def lookup_table(
        self,
        query: str | None = None,
        columns: dict[str, str] | None = None,
        manual: str | None = None,
        figure: str | None = None,
        limit: int = 10,
        block_id: str | None = None,
    ) -> list[RowHit]:
        """Rows matching all given conditions, each with its table's header and boxes.
        ``query``: words that must all appear in the row (ranked by BM25).
        ``columns``: {header words: exact cell value}, header matched loosely."""
        sql = (
            "SELECT r.table_id, t.manual, t.page, t.block_id, r.row, t.header, r.cells,"
            " r.cell_boxes, r.row_box, r.grp, r.figure FROM rows r"
            " JOIN tables t ON t.table_id = r.table_id"
        )
        where, args = [], []
        if query:
            terms = [w for w in re.findall(r"[\w.\-]+", query) if w.strip("-.")]
            if not terms:
                return []
            sql += " JOIN rows_fts f ON f.rowid = r.id"
            where.append("rows_fts MATCH ?")
            args.append(" AND ".join(f'"{w}"' for w in terms))
        if manual:
            where.append("r.manual = ?")
            args.append(manual)
        if figure:
            where.append("r.figure = ?")
            args.append(str(figure))
        if block_id:
            where.append("r.table_id = ?")
            args.append(block_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += (
            " ORDER BY bm25(rows_fts)" if query else " ORDER BY t.manual, t.page, r.row"
        )
        hits = []
        for row in self.db.execute(sql, args):
            header, cells = json.loads(row[5]), json.loads(row[6])
            if columns and not _columns_match(header, cells, columns):
                continue
            hits.append(
                RowHit(
                    table_id=row[0],
                    manual=row[1],
                    page=row[2],
                    block_id=row[3],
                    row=row[4],
                    header=header,
                    cells=cells,
                    cell_boxes=[_box(b) for b in json.loads(row[7])],
                    row_box=_box(row[8]),
                    group=row[9],
                    figure=row[10],
                )
            )
            if len(hits) >= limit:
                break
        return hits


def _value_key(text: str) -> str:
    """Cell values compared without surrounding marks: scans add stray primes ("16'")
    and parts lists indent descriptions with dots (". CAP,FILLER")."""
    return norm(text).strip(" .,;:'\"`\u2019")


def _columns_match(
    header: list[str], cells: list[str], columns: dict[str, str]
) -> bool:
    for key, value in columns.items():
        cols = [
            i
            for i, label in enumerate(header)
            if label and fuzz.partial_ratio(norm(key), norm(label)) >= HEADER_MATCH_MIN
        ]
        if not any(_value_key(cells[i]) == _value_key(value) for i in cols):
            return False
    return True
