/* Sortieren und Filtern direkt in den Spaltenköpfen, komplett im Browser.
 *
 * Aktivierung: <table class="data-table"> und pro Spalte im <th>
 *   data-col="text"     Sortieren nach Text; Filter mit Suchfeld und Werteliste
 *   data-col="number"   Sortieren nach Zahl; Filter mit von/bis
 *   data-col="date"     Sortieren nach Datum; Filter mit von/bis (Datumsauswahl)
 *   (ohne data-col)     Spalte bleibt unverändert (z. B. Aktionen)
 *   data-list="off"     bei "text" ohne Werteliste (lange Texte)
 * Pro Zelle optional: data-value="..." (Wert für Filter und Werteliste),
 *   data-sort="..." (Sortierwert; Zahl mit Punkt bzw. ISO-Datum "2026-09-19T10:00:00", leer = kein Wert).
 * Checkboxen in einer Zelle zählen als "Ja" / "Nein".
 */
(function () {
    'use strict';

    const LIST_MAX = 40;   // mehr verschiedene Werte: nur Suchfeld, keine Werteliste
    const collator = new Intl.Collator('de', { numeric: true, sensitivity: 'base' });
    const FUNNEL = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1 2h14l-5.5 6.5V14l-3-1.5V8.5z"/></svg>';

    let openPop = null;   // { el, col }

    function cellText(td) {
        if (!td) return '';
        if (td.dataset.value !== undefined) return td.dataset.value;
        const box = td.querySelector('input[type=checkbox]');
        if (box) return box.checked ? 'Ja' : 'Nein';
        return td.textContent.replace(/\s+/g, ' ').trim();
    }

    function toNumber(raw) {
        const text = String(raw === undefined || raw === null ? '' : raw).trim().replace(',', '.');
        if (text === '') return null;
        const n = Number(text);
        return Number.isFinite(n) ? n : null;
    }

    function cellNumber(td) {
        if (!td) return null;
        return toNumber(td.dataset.sort !== undefined ? td.dataset.sort : cellText(td));
    }

    function cellDate(td) {
        const raw = td && td.dataset.sort;
        if (!raw) return null;
        const time = Date.parse(raw);
        return Number.isNaN(time) ? null : time;
    }

    // Ende des Tages, damit "bis 19.09." auch Einträge vom 19.09. um 15 Uhr einschließt
    function dayBoundary(value, endOfDay) {
        return Date.parse(value + (endOfDay ? 'T23:59:59.999' : 'T00:00:00'));
    }

    function cellSortText(td) {
        if (!td) return null;
        const text = td.dataset.sort !== undefined ? td.dataset.sort : cellText(td);
        return text === '' ? null : text;
    }

    function closePop() {
        if (openPop) {
            openPop.el.remove();
            openPop = null;
        }
    }

    function initTable(table) {
        const headRow = table.tHead && table.tHead.rows[0];
        const body = table.tBodies[0];
        if (!headRow || !body) return;

        const rows = Array.from(body.rows);
        const origin = new Map(rows.map((row, i) => [row, i]));
        const columnCount = headRow.cells.length;
        const cols = [];

        const emptyRow = document.createElement('tr');
        emptyRow.className = 'dt-empty';
        emptyRow.hidden = true;
        emptyRow.innerHTML = '<td colspan="' + columnCount + '">Keine Treffer für die gewählten Filter.</td>';
        body.appendChild(emptyRow);

        const bar = document.createElement('div');
        bar.className = 'dt-bar';
        bar.hidden = true;
        bar.innerHTML = '<span class="dt-count"></span><button type="button" class="dt-reset">Filter zurücksetzen</button>';
        const anchor = table.closest('.table-responsive') || table;
        anchor.parentNode.insertBefore(bar, anchor);
        bar.querySelector('.dt-reset').addEventListener('click', () => {
            cols.forEach(clearFilter);
            closePop();
            applyFilters();
        });

        function clearFilter(col) {
            col.textRaw = '';
            col.text = '';
            col.values = null;
            col.min = null;
            col.max = null;
            col.minRaw = '';
            col.maxRaw = '';
        }

        function cellValue(col, td) {
            return col.type === 'date' ? cellDate(td) : cellNumber(td);
        }

        function isFiltered(col) {
            return col.text !== '' || col.values !== null || col.min !== null || col.max !== null;
        }

        function matches(col, td) {
            if (col.type !== 'text') {
                if (col.min === null && col.max === null) return true;
                const n = cellValue(col, td);
                if (n === null) return false;
                return (col.min === null || n >= col.min) && (col.max === null || n <= col.max);
            }
            const value = cellText(td);
            if (col.text && !value.toLowerCase().includes(col.text)) return false;
            if (col.values && !col.values.has(value)) return false;
            return true;
        }

        function applyFilters() {
            let shown = 0;
            rows.forEach(row => {
                const ok = cols.every(col => matches(col, row.cells[col.index]));
                row.hidden = !ok;
                if (ok) shown++;
            });
            emptyRow.hidden = shown !== 0 || rows.length === 0;
            const filtered = cols.some(isFiltered);
            bar.hidden = !filtered;
            bar.querySelector('.dt-count').textContent = shown + ' von ' + rows.length + ' Einträgen';
            cols.forEach(col => col.button.classList.toggle('active', isFiltered(col)));
            table.dispatchEvent(new CustomEvent('dt:filtered'));   // Seiten können auf die sichtbaren Zeilen reagieren
        }

        function sortRows() {
            const active = cols.find(col => col.sort);
            let ordered = rows.slice();
            if (active) {
                const dir = active.sort === 'asc' ? 1 : -1;
                const keys = new Map(rows.map(row => {
                    const td = row.cells[active.index];
                    return [row, active.type === 'text' ? cellSortText(td) : cellValue(active, td)];
                }));
                ordered.sort((a, b) => {
                    const ka = keys.get(a), kb = keys.get(b);
                    if (ka === null && kb === null) return origin.get(a) - origin.get(b);
                    if (ka === null) return 1;           // leere Werte immer ans Ende
                    if (kb === null) return -1;
                    const diff = active.type === 'text' ? collator.compare(ka, kb) : ka - kb;
                    return diff !== 0 ? diff * dir : origin.get(a) - origin.get(b);
                });
            }
            ordered.forEach(row => body.appendChild(row));
            body.appendChild(emptyRow);
        }

        function cycleSort(col) {
            const next = col.sort === null ? 'asc' : (col.sort === 'asc' ? 'desc' : null);
            cols.forEach(c => {
                c.sort = null;
                c.th.classList.remove('dt-sorted');
                c.th.removeAttribute('aria-sort');
                c.arrow.textContent = '↕';
            });
            if (next) {
                col.sort = next;
                col.th.classList.add('dt-sorted');
                col.th.setAttribute('aria-sort', next === 'asc' ? 'ascending' : 'descending');
                col.arrow.textContent = next === 'asc' ? '▲' : '▼';
            }
            sortRows();
        }

        function distinctValues(col) {
            const values = new Set(rows.map(row => cellText(row.cells[col.index])));
            return Array.from(values).sort((a, b) => collator.compare(a, b));
        }

        function buildTextPopover(pop, col) {
            const search = document.createElement('input');
            search.type = 'text';
            search.placeholder = 'Suchen …';
            search.value = col.textRaw;
            search.addEventListener('input', () => {
                col.textRaw = search.value;
                col.text = search.value.trim().toLowerCase();
                applyFilters();
            });
            pop.appendChild(search);

            if (col.list) {
                const values = distinctValues(col);
                if (values.length > 1 && values.length <= LIST_MAX) {
                    const list = document.createElement('div');
                    list.className = 'dt-list';
                    const boxes = [];
                    const sync = () => {
                        const checked = boxes.filter(b => b.checked).map(b => b.dataset.value);
                        col.values = checked.length === boxes.length ? null : new Set(checked);
                        allBox.checked = checked.length === boxes.length;
                        allBox.indeterminate = checked.length > 0 && checked.length < boxes.length;
                        applyFilters();
                    };
                    const allLabel = document.createElement('label');
                    allLabel.className = 'dt-all';
                    const allBox = document.createElement('input');
                    allBox.type = 'checkbox';
                    allLabel.append(allBox, Object.assign(document.createElement('span'), { textContent: '(Alle)' }));
                    allBox.addEventListener('change', () => {
                        boxes.forEach(b => { b.checked = allBox.checked; });
                        sync();
                    });
                    list.appendChild(allLabel);
                    values.forEach(value => {
                        const label = document.createElement('label');
                        const box = document.createElement('input');
                        box.type = 'checkbox';
                        box.dataset.value = value;
                        box.checked = !col.values || col.values.has(value);
                        box.addEventListener('change', sync);
                        boxes.push(box);
                        label.append(box, Object.assign(document.createElement('span'), { textContent: value === '' ? '(leer)' : value }));
                        list.appendChild(label);
                    });
                    allBox.checked = boxes.every(b => b.checked);
                    allBox.indeterminate = !allBox.checked && boxes.some(b => b.checked);
                    pop.appendChild(list);
                }
            }
            return search;
        }

        function buildRangePopover(pop, col) {
            const isDate = col.type === 'date';
            const range = document.createElement('div');
            range.className = isDate ? 'dt-range dt-range-date' : 'dt-range';
            const make = (title, key, endOfDay) => {
                const input = document.createElement('input');
                if (isDate) {
                    input.type = 'date';
                } else {
                    input.type = 'text';
                    input.inputMode = 'decimal';
                    input.placeholder = title;
                }
                input.value = col[key + 'Raw'];
                input.addEventListener('input', () => {
                    col[key + 'Raw'] = input.value;
                    if (isDate) col[key] = input.value ? dayBoundary(input.value, endOfDay) : null;
                    else col[key] = toNumber(input.value);
                    applyFilters();
                });
                if (!isDate) return input;
                const label = document.createElement('label');
                label.append(Object.assign(document.createElement('span'), { textContent: title }), input);
                return label;
            };
            const from = make('von', 'min', false);
            const to = make('bis', 'max', true);
            range.append(from, to);
            pop.appendChild(range);
            return isDate ? from.querySelector('input') : from;
        }

        function openPopover(col) {
            if (openPop && openPop.col === col) {
                closePop();
                return;
            }
            closePop();
            const pop = document.createElement('div');
            pop.className = 'dt-pop';
            const first = col.type === 'text' ? buildTextPopover(pop, col) : buildRangePopover(pop, col);

            const actions = document.createElement('div');
            actions.className = 'dt-pop-actions';
            const reset = document.createElement('button');
            reset.type = 'button';
            reset.textContent = 'Zurücksetzen';
            reset.addEventListener('click', () => {
                clearFilter(col);
                applyFilters();
                closePop();
                openPopover(col);
            });
            actions.appendChild(reset);
            pop.appendChild(actions);

            document.body.appendChild(pop);
            const rect = col.button.getBoundingClientRect();
            const left = Math.min(rect.left, window.innerWidth - pop.offsetWidth - 8);
            pop.style.left = Math.max(8, left) + window.scrollX + 'px';
            pop.style.top = rect.bottom + window.scrollY + 4 + 'px';
            openPop = { el: pop, col };
            first.focus({ preventScroll: true });
        }

        Array.from(headRow.cells).forEach((th, index) => {
            const type = th.dataset.col;
            if (type !== 'text' && type !== 'number' && type !== 'date') return;

            const label = document.createElement('span');
            label.className = 'dt-label';
            label.tabIndex = 0;
            while (th.firstChild) label.appendChild(th.firstChild);
            const arrow = document.createElement('span');
            arrow.className = 'dt-arrow';
            arrow.textContent = '↕';
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'dt-filter-btn';
            button.title = 'Filtern';
            button.innerHTML = FUNNEL;
            const head = document.createElement('div');
            head.className = 'dt-head';
            head.append(label, arrow, button);
            th.appendChild(head);

            const col = { index, th, type, arrow, button, sort: null, list: th.dataset.list !== 'off' };
            clearFilter(col);
            cols.push(col);

            const onSort = event => {
                if (event.target.closest('input, label, a, button')) return;   // z. B. "Alle"-Checkbox im Kopf
                cycleSort(col);
            };
            label.addEventListener('click', onSort);
            arrow.addEventListener('click', onSort);
            label.addEventListener('keydown', event => {
                if (event.key === 'Enter' && event.target === label) cycleSort(col);
            });
            button.addEventListener('click', event => {
                event.stopPropagation();
                openPopover(col);
            });
        });
    }

    document.addEventListener('mousedown', event => {
        if (openPop && !openPop.el.contains(event.target) && !event.target.closest('.dt-filter-btn')) closePop();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closePop();
    });
    window.addEventListener('scroll', event => {
        if (openPop && !openPop.el.contains(event.target)) closePop();
    }, true);
    window.addEventListener('resize', closePop);

    document.querySelectorAll('table.data-table').forEach(initTable);
})();
