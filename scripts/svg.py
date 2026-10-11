"""Tiny inline-SVG chart kit (no dependencies). Marks carry data-tip for the shared tooltip script.
Colours are CSS variables defined in assets/style.css (light/dark tokens)."""
import html, math

E = html.escape


def _nice(vmax, n=4):
    if vmax <= 0:
        return [0, 1]
    raw = vmax / n; mag = 10 ** math.floor(math.log10(raw)); st = mag
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            st = m * mag; break
    top = math.ceil(vmax / st) * st
    return [round(i * st, 6) for i in range(int(round(top / st)) + 1)]


def fmt(v):
    if v is None:
        return ''
    if abs(v) >= 10000:
        return f'{v / 1000:.0f} tis.'.replace('.', ',') if abs(v) >= 100000 else f'{v:,.0f}'.replace(',', ' ')
    if float(v).is_integer():
        return f'{int(v):,}'.replace(',', ' ')
    return f'{v:.2f}'.replace('.', ',')


def table(headers, rows):
    h = ''.join(f'<th>{E(str(x))}</th>' for x in headers)
    b = ''.join('<tr>' + ''.join(f'<td>{E(str(c))}</td>' for c in r) + '</tr>' for r in rows)
    return f'<details class="tableview"><summary>Zobrazit jako tabulku</summary><div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div></details>'


def legend(items):
    """items: list of (label, css_var, kind) kind in rect|line|dot|ring"""
    out = []
    for lab, var, kind in items:
        if kind == 'line':
            sw = f'<svg width="18" height="10" aria-hidden="true"><line x1="1" y1="5" x2="17" y2="5" stroke="var({var})" stroke-width="2" stroke-linecap="round"/></svg>'
        elif kind == 'dot':
            sw = f'<svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill="var({var})"/></svg>'
        elif kind == 'ring':
            sw = f'<svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4" fill="none" stroke="var({var})" stroke-width="2"/></svg>'
        else:
            sw = f'<svg width="12" height="12" aria-hidden="true"><rect x="1" y="1" width="10" height="10" rx="2" fill="var({var})"/></svg>'
        out.append(f'<span class="lg">{sw}{E(lab)}</span>')
    return '<div class="legend">' + ''.join(out) + '</div>'


def hbars(cats, series, colors, width=1060, bar=14, gap=6, label_w=230, unit='', value_fmt=fmt, ticks=None):
    """Grouped horizontal bars. series: list of (name, values)."""
    ns = len(series); band = ns * bar + (ns - 1) * 2 + gap * 2
    h = band * len(cats) + 28
    vmax = max([v for _, vals in series for v in vals if v is not None] + [1])
    tk = ticks or _nice(vmax)
    plot_w = width - label_w - 50
    sx = lambda v: label_w + plot_w * v / tk[-1]
    parts = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img">']
    for t in tk:
        parts.append(f'<line x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="0" y2="{h - 22}" class="grid"/>'
                     f'<text x="{sx(t):.1f}" y="{h - 6}" class="tick" text-anchor="middle">{E(value_fmt(t))}</text>')
    for i, c in enumerate(cats):
        y0 = i * band + gap
        parts.append(f'<text x="{label_w - 8}" y="{y0 + band / 2 - gap + 4:.1f}" class="lab" text-anchor="end">{E(c)}</text>')
        for j, (name, vals) in enumerate(series):
            v = vals[i]
            if v is None:
                continue
            y = y0 + j * (bar + 2); w = max(sx(v) - label_w, 0)
            r = min(4, w / 2)
            path = (f'M{label_w},{y} h{max(w - r, 0):.1f} a{r},{r} 0 0 1 {r},{r} v{bar - 2 * r} a{r},{r} 0 0 1 -{r},{r} h-{max(w - r, 0):.1f} z'
                    if w > 0 else '')
            tip = f'{c} · {name}: {value_fmt(v)}{unit}'
            parts.append(f'<g class="mk" tabindex="0" data-tip="{E(tip)}"><rect x="{label_w}" y="{y - 1}" width="{plot_w}" height="{bar + 2}" class="hit"/>'
                         f'<path d="{path}" fill="var({colors[j]})"/></g>')
            parts.append(f'<text x="{sx(v) + 5:.1f}" y="{y + bar - 3}" class="val">{E(value_fmt(v))}</text>')
    parts.append(f'<line x1="{label_w}" x2="{label_w}" y1="0" y2="{h - 22}" class="axis"/></svg>')
    return ''.join(parts)


def lines(xs, series, colors, width=1060, height=300, xlabel='', ylabel='', highlight=None, ymax=None):
    """Line chart: series list of (name, values). highlight: (x, label) vertical marker."""
    L, R, T, B = 48, 16, 12, 34
    pw, ph = width - L - R, height - T - B
    vmax = ymax or max(max(v for v in vals if v is not None) for _, vals in series)
    tk = _nice(vmax)
    sx = lambda i: L + pw * (i - xs[0]) / max(xs[-1] - xs[0], 1)
    sy = lambda v: T + ph - ph * v / tk[-1]
    p = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for t in tk:
        p.append(f'<line x1="{L}" x2="{L + pw}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="grid"/><text x="{L - 6}" y="{sy(t) + 4:.1f}" class="tick" text-anchor="end">{E(fmt(t))}</text>')
    step = max(1, len(xs) // 10)
    for x in xs[::step]:
        p.append(f'<text x="{sx(x):.1f}" y="{T + ph + 16}" class="tick" text-anchor="middle">{x}</text>')
    if xlabel:
        p.append(f'<text x="{L + pw / 2}" y="{height - 2}" class="tick" text-anchor="middle">{E(xlabel)}</text>')
    if ylabel:
        p.append(f'<text x="12" y="{T + ph / 2}" class="tick" text-anchor="middle" transform="rotate(-90 12 {T + ph / 2})">{E(ylabel)}</text>')
    if highlight:
        hx, hl = highlight
        p.append(f'<line x1="{sx(hx):.1f}" x2="{sx(hx):.1f}" y1="{T}" y2="{T + ph}" class="hl"/><text x="{sx(hx) + 4:.1f}" y="{T + 10}" class="lab">{E(hl)}</text>')
    for j, (name, vals) in enumerate(series):
        pts = ' '.join(f'{sx(x):.1f},{sy(v):.1f}' for x, v in zip(xs, vals) if v is not None)
        p.append(f'<polyline points="{pts}" fill="none" stroke="var({colors[j]})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    # hover columns (crosshair-like): one hit rect per x with all series values
    cw = pw / max(len(xs) - 1, 1)
    for i, x in enumerate(xs):
        tip = f'{xlabel} {x}: ' + '; '.join(f'{n} {fmt(vals[i])}' for n, vals in series if vals[i] is not None)
        p.append(f'<rect x="{sx(x) - cw / 2:.1f}" y="{T}" width="{cw:.1f}" height="{ph}" class="hit col" tabindex="0" data-tip="{E(tip)}"/>')
    p.append(f'<line x1="{L}" x2="{L + pw}" y1="{T + ph}" y2="{T + ph}" class="axis"/></svg>')
    return ''.join(p)


def columns(cats, vals, color='--series-1', width=1060, height=280, highlight=None, ylabel='', tips=None, xlab_every=None, expected=None, small=False):
    """Vertical columns; highlight: set of category indices drawn in --critical; expected: list of marker values."""
    L, R, T, B = 48, 10, 12, 40
    pw, ph = width - L - R, height - T - B
    vmax = max([v for v in vals] + ([e for e in expected if e is not None] if expected else []) + [1])
    tk = _nice(vmax); n = len(cats)
    bw = min(24, pw / n * 0.72); slot = pw / n
    sy = lambda v: T + ph - ph * v / tk[-1]
    p = [f'<svg viewBox="0 0 {width} {height}" class="chart{" sm" if small else ""}" role="img">']
    for t in tk:
        p.append(f'<line x1="{L}" x2="{L + pw}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="grid"/><text x="{L - 6}" y="{sy(t) + 4:.1f}" class="tick" text-anchor="end">{E(fmt(t))}</text>')
    if ylabel:
        p.append(f'<text x="12" y="{T + ph / 2}" class="tick" text-anchor="middle" transform="rotate(-90 12 {T + ph / 2})">{E(ylabel)}</text>')
    every = xlab_every or max(1, n // 12)
    for i, (c, v) in enumerate(zip(cats, vals)):
        x = L + i * slot + (slot - bw) / 2; y = sy(max(v, 0)); hgt = T + ph - y
        r = min(4, bw / 2, hgt)
        col = 'var(--critical)' if highlight and i in highlight else f'var({color})'
        d = f'M{x:.1f},{T + ph} v-{max(hgt - r, 0):.1f} a{r},{r} 0 0 1 {r},-{r} h{bw - 2 * r:.1f} a{r},{r} 0 0 1 {r},{r} v{max(hgt - r, 0):.1f} z' if hgt > 0 else ''
        tip = tips[i] if tips else f'{c}: {fmt(v)}'
        p.append(f'<g class="mk" tabindex="0" data-tip="{E(tip)}"><rect x="{L + i * slot:.1f}" y="{T}" width="{slot:.1f}" height="{ph}" class="hit"/><path d="{d}" fill="{col}"/></g>')
        if expected and expected[i] is not None:
            ey = sy(expected[i])
            p.append(f'<line x1="{x - 2:.1f}" x2="{x + bw + 2:.1f}" y1="{ey:.1f}" y2="{ey:.1f}" class="expmark"/>')
        if i % every == 0 or (highlight and i in highlight):
            p.append(f'<text x="{x + bw / 2:.1f}" y="{T + ph + 14}" class="tick" text-anchor="end" transform="rotate(-35 {x + bw / 2:.1f} {T + ph + 14})">{E(str(c))}</text>')
    p.append(f'<line x1="{L}" x2="{L + pw}" y1="{T + ph}" y2="{T + ph}" class="axis"/></svg>')
    return ''.join(p)


def hist(values, bins, flagged=None, width=1060, height=240, xlabel='', color='--series-1', min_h=0, thr=None, rug=None, rug_label=''):
    """Lineární histogram. min_h: minimální výška neprázdného sloupce v px (aby osamělé hodnoty nezmizely).
    thr: (hodnota, popisek) svislá čára prahu. rug: seznam (hodnota, css_var, tooltip) – jednotlivé záznamy
    jako tečky v pásu pod osou (skládané nad sebe), pro řídké chvosty, které by v lineárním histogramu zanikly."""
    import numpy as np
    c, e = np.histogram(values, bins=bins)
    fc = np.histogram(flagged, bins=bins)[0] if flagged is not None and len(flagged) else np.zeros_like(c)
    L, R, T, B = 48, 10, 12, 36
    pw, ph = width - L - R, height - T - B
    sx = lambda v: L + pw * (v - e[0]) / (e[-1] - e[0])
    dots, lane = [], 0
    if rug:
        step = 8
        cols = {}
        for v, var, tip in sorted(rug, key=lambda t: (t[1] != '--critical', t[0])):
            k = int(round((sx(min(max(v, e[0]), e[-1])) - L) / step)); n = cols.get(k, 0); cols[k] = n + 1
            dots.append((L + k * step, n, var, tip))
        lane = 20 + max(cols.values()) * step
        height += lane
    H0 = height - lane
    bar = lambda n: (T + ph - max(ph * n / tk[-1], min_h if n else 0))
    tk = _nice(max(c.max(), 1)); sy = lambda v: T + ph - ph * v / tk[-1]
    p = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for t in tk:
        p.append(f'<line x1="{L}" x2="{L + pw}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="grid"/><text x="{L - 6}" y="{sy(t) + 4:.1f}" class="tick" text-anchor="end">{E(fmt(t))}</text>')
    for i in range(len(c)):
        x0, x1 = sx(e[i]) + 1, sx(e[i + 1]) - 1
        if c[i] > 0:
            p.append(f'<g class="mk" tabindex="0" data-tip="{E(f"{e[i]:.2f}–{e[i + 1]:.2f}: {c[i]} okrsků" + (f" (z toho podezřelé {fc[i]})" if fc[i] else ""))}">'
                     f'<rect x="{x0:.1f}" y="{T}" width="{max(x1 - x0, 1):.1f}" height="{ph}" class="hit"/>'
                     f'<rect x="{x0:.1f}" y="{bar(c[i]):.1f}" width="{max(x1 - x0, 1):.1f}" height="{T + ph - bar(c[i]):.1f}" fill="var({color})" rx="1"/>'
                     + (f'<rect x="{x0:.1f}" y="{bar(fc[i]):.1f}" width="{max(x1 - x0, 1):.1f}" height="{T + ph - bar(fc[i]):.1f}" fill="var(--critical)" rx="1"/>' if fc[i] else '') + '</g>')
    for t in _nice(e[-1] - e[0], 6):
        v = e[0] + t
        if v <= e[-1] + 1e-9:
            p.append(f'<text x="{sx(v):.1f}" y="{T + ph + 16}" class="tick" text-anchor="middle">{E(fmt(round(v, 3)))}</text>')
    if xlabel:
        p.append(f'<text x="{L + pw / 2}" y="{H0 - 2}" class="tick" text-anchor="middle">{E(xlabel)}</text>')
    if thr is not None:
        xt = sx(thr[0])
        p.append(f'<line x1="{xt:.1f}" x2="{xt:.1f}" y1="{T}" y2="{H0 + lane - 4 if lane else T + ph}" stroke="var(--ink2)" stroke-width="1" stroke-dasharray="4 3"/>'
                 f'<text x="{xt + 6:.1f}" y="{T + 10}" class="lab">{E(thr[1])}</text>')
    if dots:
        p.append(f'<text x="{L}" y="{H0 + 12}" class="lab">{E(rug_label)}</text>')
        for x, n, var, tip in dots:
            p.append(f'<g class="mk" tabindex="0" data-tip="{E(tip)}"><circle cx="{x:.1f}" cy="{H0 + 24 + n * 8:.1f}" r="6" class="hit"/>'
                     f'<circle cx="{x:.1f}" cy="{H0 + 24 + n * 8:.1f}" r="3.5" fill="var({var})" stroke="var(--surface)" stroke-width="1.5"/></g>')
    p.append(f'<line x1="{L}" x2="{L + pw}" y1="{T + ph}" y2="{T + ph}" class="axis"/></svg>')
    return ''.join(p)


def scatter(pts, width=520, height=380, xlabel='', ylabel='', xmax=1.0, ymax=0.6, color='--series-1', title=''):
    L, R, T, B = 58, 24, 22, 34
    pw, ph = width - L - R, height - T - B
    sx = lambda v: L + pw * v / xmax; sy = lambda v: T + ph - ph * v / ymax
    p = [f'<svg viewBox="0 0 {width} {height}" class="chart sm" role="img">']
    if title:
        p.append(f'<text x="{L}" y="12" class="lab">{E(title)}</text>')
    for t in _nice(ymax, 3):
        if t <= ymax:
            p.append(f'<line x1="{L}" x2="{L + pw}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="grid"/><text x="{L - 6}" y="{sy(t) + 4:.1f}" class="tick" text-anchor="end">{int(t * 100)} %</text>')
    for t in _nice(xmax, 4):
        if t <= xmax:
            p.append(f'<text x="{sx(t):.1f}" y="{T + ph + 14}" class="tick" text-anchor="middle">{int(t * 100)} %</text>')
    for x, y, n in pts:
        p.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="2.2" fill="var({color})" fill-opacity="0.55"/>')
    p.append(f'<text x="{L + pw / 2}" y="{height - 2}" class="tick" text-anchor="middle">{E(xlabel)}</text>')
    p.append(f'<text x="11" y="{T + ph / 2}" class="tick" text-anchor="middle" transform="rotate(-90 11 {T + ph / 2})">{E(ylabel)}</text>')
    p.append(f'<line x1="{L}" x2="{L + pw}" y1="{T + ph}" y2="{T + ph}" class="axis"/></svg>')
    return ''.join(p)


def diverging(cats, vals, width=1060, bar=14, label_w=360):
    gap = 8; h = (bar + gap) * len(cats) + 26
    vmax = max(abs(v) for v in vals) or 1; tk = _nice(vmax, 3)
    pw = (width - label_w - 60) / 2; cx = label_w + pw + 10
    sx = lambda v: cx + pw * v / tk[-1]
    p = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img">']
    for t in tk[1:]:
        for s in (-1, 1):
            p.append(f'<line x1="{sx(s * t):.1f}" x2="{sx(s * t):.1f}" y1="0" y2="{h - 22}" class="grid"/><text x="{sx(s * t):.1f}" y="{h - 6}" class="tick" text-anchor="middle">{E(("+" if s > 0 else "−") + fmt(t))}</text>')
    for i, (c, v) in enumerate(zip(cats, vals)):
        y = i * (bar + gap) + 4
        x0, x1 = sorted((cx, sx(v)))
        col = 'var(--div-pos)' if v > 0 else 'var(--div-neg)'
        p.append(f'<text x="{label_w - 8}" y="{y + bar - 3}" class="lab" text-anchor="end">{E(c)}</text>')
        p.append(f'<g class="mk" tabindex="0" data-tip="{E(c)}: {("+" if v > 0 else "")}{E(fmt(v))} hlasů"><rect x="{label_w}" y="{y - 2}" width="{width - label_w}" height="{bar + 4}" class="hit"/>'
                 f'<rect x="{x0:.1f}" y="{y}" width="{max(x1 - x0, 1):.1f}" height="{bar}" rx="3" fill="{col}"/></g>')
        p.append(f'<text x="{(x1 + 5) if v > 0 else (x0 - 5):.1f}" y="{y + bar - 3}" class="val" text-anchor="{"start" if v > 0 else "end"}">{("+" if v > 0 else "")}{E(fmt(v))}</text>')
    p.append(f'<line x1="{cx}" x2="{cx}" y1="0" y2="{h - 22}" class="axis"/></svg>')
    return ''.join(p)
