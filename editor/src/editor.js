// CodeMirror 6 editor for ManimGX Studio. Colors come from the app's CSS variables, so light/dark follow the theme.
import { EditorState, StateField, StateEffect, RangeSet, Annotation } from '@codemirror/state';
import {
  EditorView, keymap, lineNumbers, lineNumberMarkers, GutterMarker, highlightActiveLine, highlightActiveLineGutter,
  drawSelection, dropCursor, Decoration, highlightSpecialChars, hoverTooltip,
} from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab, undo, redo, selectAll, undoDepth, redoDepth } from '@codemirror/commands';
import { bracketMatching, indentOnInput, syntaxHighlighting, HighlightStyle, indentUnit } from '@codemirror/language';
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from '@codemirror/autocomplete';
import { searchKeymap, highlightSelectionMatches, openSearchPanel } from '@codemirror/search';
import { python } from '@codemirror/lang-python';
import { tags as t } from '@lezer/highlight';
import names from '../names.json';
import { KEYWORDS, NAMES, PARAMS } from './explain.js';

/* ---------- look ---------- */
const style = HighlightStyle.define([
  { tag: [t.keyword, t.controlKeyword, t.definitionKeyword, t.moduleKeyword, t.operatorKeyword, t.self, t.bool, t.null], color: 'var(--t-kw)' },
  { tag: [t.string, t.special(t.string)], color: 'var(--t-str)' },
  { tag: [t.number, t.integer, t.float], color: 'var(--t-num)' },
  { tag: [t.comment, t.lineComment, t.blockComment], color: 'var(--t-com)', fontStyle: 'italic' },
  { tag: [t.className, t.typeName, t.definition(t.className)], color: 'var(--t-cls)' },
  { tag: [t.function(t.variableName), t.function(t.propertyName), t.definition(t.function(t.variableName)), t.macroName, t.meta], color: 'var(--t-fn)' },
  { tag: [t.invalid], color: 'var(--danger)' },
]);

const theme = EditorView.theme({
  '&': { height: '100%', color: 'var(--text)', backgroundColor: 'var(--code-bg)', fontSize: 'var(--code-fs, 13.5px)' },
  '&.cm-focused': { outline: 'none' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.65', overflow: 'auto', overscrollBehavior: 'contain' },
  '.cm-content': { padding: '14px 0', caretColor: 'var(--accent)' },
  '.cm-line': { padding: '0 18px' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--accent)', borderLeftWidth: '2px' },
  '.cm-selectionBackground': { background: 'color-mix(in oklch, var(--accent) 22%, transparent) !important' },
  '&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground': { background: 'color-mix(in oklch, var(--accent) 32%, transparent) !important' },
  '.cm-activeLine': { backgroundColor: 'color-mix(in oklch, var(--accent) 6%, transparent)' },
  '.cm-selectionMatch': { backgroundColor: 'color-mix(in oklch, var(--accent) 16%, transparent)' },
  '.cm-matchingBracket, &.cm-focused .cm-matchingBracket': { backgroundColor: 'color-mix(in oklch, var(--accent) 24%, transparent)', outline: '1px solid color-mix(in oklch, var(--accent) 55%, transparent)', color: 'inherit' },
  '.cm-nonmatchingBracket, &.cm-focused .cm-nonmatchingBracket': { backgroundColor: 'color-mix(in oklch, var(--danger) 25%, transparent)', color: 'inherit' },
  '.cm-gutters': { backgroundColor: 'var(--code-bg)', color: 'var(--gutter)', border: 'none', borderRight: '1px solid var(--line)' },
  '.cm-lineNumbers .cm-gutterElement': { padding: '0 12px 0 22px', minWidth: '3.4ch', position: 'relative', fontVariantNumeric: 'tabular-nums' },
  '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--text-2)' },
  '.cm-gutterElement.mgx-warn': { color: 'var(--warn)', fontWeight: '700' },
  '.cm-gutterElement.mgx-err': { color: 'var(--danger)', fontWeight: '700' },
  '.cm-gutterElement.mgx-warn::before, .cm-gutterElement.mgx-err::before': { content: '""', position: 'absolute', left: '11px', top: '50%', marginTop: '-2.5px', width: '5px', height: '5px', borderRadius: '50%', background: 'currentColor' },
  '.mgx-flash': { animation: 'mgx-flash 1.5s ease-out 1' },
  '@keyframes mgx-flash': { from: { backgroundColor: 'color-mix(in oklch, var(--accent) 34%, transparent)' }, to: { backgroundColor: 'transparent' } },

  '.cm-tooltip': { backgroundColor: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--line)', borderRadius: '10px', boxShadow: 'var(--sh-pop)', overflow: 'hidden' },
  '.cm-tooltip.cm-tooltip-autocomplete > ul': { fontFamily: 'var(--font-mono)', fontSize: '13px', maxHeight: '15em', padding: '4px' },
  '.cm-tooltip.cm-tooltip-autocomplete > ul > li': { padding: '3px 8px', borderRadius: '6px', lineHeight: '1.6' },
  '.cm-tooltip-autocomplete ul li[aria-selected]': { backgroundColor: 'var(--accent-soft)', color: 'var(--text)' },
  '.cm-completionLabel': { color: 'var(--text)' },
  '.cm-completionMatchedText': { textDecoration: 'none', fontWeight: '700', color: 'var(--accent-text)' },
  '.cm-completionDetail': { color: 'var(--text-3)', fontStyle: 'normal', marginLeft: '.7em', maxWidth: '34ch', overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block', verticalAlign: 'bottom', whiteSpace: 'nowrap' },
  '.cm-completionInfo': { fontFamily: 'var(--font-ui)', fontSize: '12.5px', padding: '8px 12px', maxWidth: '34ch', color: 'var(--text-2)', lineHeight: '1.45' },
  '.cm-completionIcon': { color: 'var(--text-3)', opacity: '1' },

  '.cm-tooltip.cm-tooltip-hover': { maxWidth: '360px' },
  '.mgx-tip': { padding: '10px 12px', fontFamily: 'var(--font-ui)', fontSize: '12.5px', lineHeight: '1.5', color: 'var(--text-2)' },
  '.mgx-tip p': { margin: '4px 0 0' },
  '.mgx-tip-h': { display: 'flex', gap: '8px', alignItems: 'baseline' },
  '.mgx-tip-h code': { fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--text)', fontSize: '13px' },
  '.mgx-tip-h span': { color: 'var(--text-3)', fontSize: '11.5px' },
  '.mgx-tip p:nth-of-type(1)': { color: 'var(--text)' },
  '.mgx-tip-c b': { color: 'var(--accent-text)' },
  '.mgx-tip-x': { color: 'var(--text-3)', fontSize: '11.5px', borderTop: '1px solid var(--line)', paddingTop: '6px', marginTop: '8px !important' },

  '.cm-panels': { backgroundColor: 'var(--surface)', color: 'var(--text)', borderColor: 'var(--line)', fontFamily: 'var(--font-ui)', fontSize: '13px' },
  '.cm-panels.cm-panels-top': { borderBottom: '1px solid var(--line)' },
  '.cm-search': { padding: '8px 10px', display: 'flex', flexWrap: 'wrap', gap: '6px 6px', alignItems: 'center' },
  '.cm-search br': { display: 'none' },
  '.cm-search label': { display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--text-2)', fontSize: '12.5px' },
  '.cm-textfield': { background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--line-strong)', borderRadius: '8px', padding: '5px 9px', fontFamily: 'var(--font-mono)', fontSize: '13px', margin: '0' },
  '.cm-textfield:focus': { outline: '2px solid var(--accent)', outlineOffset: '1px' },
  '.cm-button': { backgroundImage: 'none', background: 'var(--surface-2)', color: 'var(--text)', border: '1px solid var(--line-strong)', borderRadius: '8px', padding: '5px 11px', fontSize: '12.5px', margin: '0', cursor: 'pointer' },
  '.cm-button:hover': { background: 'var(--surface-3)' },
  '.cm-panel.cm-search [name=close]': { color: 'var(--text-2)', fontSize: '18px', top: '6px', right: '8px' },
  '.cm-searchMatch': { backgroundColor: 'color-mix(in oklch, var(--warn) 30%, transparent)', outline: 'none' },
  '.cm-searchMatch.cm-searchMatch-selected': { backgroundColor: 'color-mix(in oklch, var(--accent) 38%, transparent)' },
});

/* ---------- gutter marks (layout notes, error line) and the "jump here" flash ---------- */
class Mark extends GutterMarker {
  constructor(cls) { super(); this.elementClass = cls; }
  eq(other) { return other.elementClass === this.elementClass; }
}
const WARN = new Mark('mgx-warn'), ERR = new Mark('mgx-err');
const setMarksEffect = StateEffect.define();
const marksField = StateField.define({
  create: () => RangeSet.empty,
  update(value, tr) {
    value = value.map(tr.changes);
    for (const e of tr.effects) if (e.is(setMarksEffect)) {
      const doc = tr.state.doc, ranges = [];
      for (const [line, kind] of Object.entries(e.value).sort((a, b) => a[0] - b[0])) {
        const n = Number(line);
        if (n >= 1 && n <= doc.lines) ranges.push((kind === 'err' ? ERR : WARN).range(doc.line(n).from));
      }
      value = RangeSet.of(ranges);
    }
    return value;
  },
  provide: (f) => lineNumberMarkers.from(f),
});
const flashEffect = StateEffect.define();
const flashField = StateField.define({
  create: () => Decoration.none,
  update(value, tr) {
    value = value.map(tr.changes);
    for (const e of tr.effects) if (e.is(flashEffect)) {
      value = e.value == null ? Decoration.none : Decoration.set([Decoration.line({ class: 'mgx-flash' }).range(tr.state.doc.line(e.value).from)]);
    }
    return value;
  },
  provide: (f) => EditorView.decorations.from(f),
});

/* ---------- autocomplete from the installed manimgx ---------- */
const KIND = { class: 'class', function: 'function', constant: 'constant', variable: 'variable', method: 'method', property: 'property' };
function option(e, boost) {
  const callable = e.k === 'class' || e.k === 'function' || e.k === 'method';
  const o = { label: e.n, type: KIND[e.k] || 'variable', boost, info: e.d || undefined, detail: e.s !== undefined ? '(' + e.s + ')' : undefined };
  if (callable) {
    o.apply = (view, _c, from, to) => {            // insert name(), cursor inside the brackets
      const open = view.state.sliceDoc(to, to + 1) === '(';
      view.dispatch({ changes: { from, to, insert: open ? e.n : e.n + '()' }, selection: { anchor: from + e.n.length + 1 }, userEvent: 'input.complete' });
    };
  }
  return o;
}
const TOP = names.top.map((e) => option(e, 0));
const SCENE = names.scene.map((e) => option(e, 0));
const MOB = names.mobject.map((e) => option(e, e.k === 'property' ? 1 : 0));

function aliases(doc) {
  const set = new Set(['manimgx']);
  for (const m of doc.matchAll(/^\s*import\s+manimgx(?:\s+as\s+(\w+))?/gm)) if (m[1]) set.add(m[1]);
  return set;
}
function manimgxSource(ctx) {
  const word = ctx.matchBefore(/[\w.]*/);
  if (!word) return null;
  const dot = word.text.lastIndexOf('.');
  if (dot >= 0) {
    const owner = word.text.slice(0, dot);
    const from = word.from + dot + 1;
    const root = owner.split('.')[0];
    let options;
    if (aliases(ctx.state.doc.toString()).has(owner)) options = TOP;
    else if (owner === 'self') options = SCENE.concat(MOB);
    else if (root === '') return null;
    else options = MOB;
    return { from, options, validFor: /^\w*$/ };
  }
  if (!ctx.explicit && word.to - word.from < 2) return null;
  const doc = ctx.state.doc.toString();
  if (/^\s*from\s+manimgx\s+import\s+\*/m.test(doc)) return { from: word.from, options: TOP, validFor: /^\w*$/ };
  const extra = [];
  for (const a of aliases(doc)) extra.push({ label: a, type: 'namespace', boost: 2 });
  extra.push({ label: 'self', type: 'keyword', boost: 2 });
  return { from: word.from, options: extra, validFor: /^\w*$/ };
}

/* ---------- hover help: what a name, option or number does, in plain words ---------- */
const BY_NAME = {};
for (const group of [names.mobject, names.scene, names.top]) for (const e of group) BY_NAME[e.n] = e;   // top-level names win
const TOP_NAMES = new Set(names.top.map((e) => e.n));
const SCENE_NAMES = new Set(names.scene.map((e) => e.n));

function paramNames(sig) {
  const out = []; let depth = 0, cur = '';
  for (const ch of (sig || '') + ',') {
    if (ch === '(' || ch === '[' || ch === '{') depth++;
    else if (ch === ')' || ch === ']' || ch === '}') depth--;
    if (ch === ',' && depth === 0) { const n = cur.trim().split('=')[0].trim(); if (n && !n.startsWith('*')) out.push(n); cur = ''; } else cur += ch;
  }
  return out;
}
function tip(title, kind, what, change, extra) {
  const dom = document.createElement('div');
  dom.className = 'mgx-tip';
  const h = document.createElement('div'); h.className = 'mgx-tip-h';
  const t = document.createElement('code'); t.textContent = title; h.appendChild(t);
  if (kind) { const k = document.createElement('span'); k.textContent = kind; h.appendChild(k); }
  dom.appendChild(h);
  const w = document.createElement('p'); w.textContent = what; dom.appendChild(w);
  if (change) { const c = document.createElement('p'); c.className = 'mgx-tip-c'; const b = document.createElement('b'); b.textContent = 'Try: '; c.appendChild(b); c.appendChild(document.createTextNode(change)); dom.appendChild(c); }
  if (extra) { const x = document.createElement('p'); x.className = 'mgx-tip-x'; x.textContent = extra; dom.appendChild(x); }
  return { dom };
}
const KIND_LABEL = { class: 'building block', function: 'function', constant: 'built-in value', method: 'action', property: 'property', variable: 'value' };

function explainAt(view, pos) {
  const line = view.state.doc.lineAt(pos), text = line.text, i = pos - line.from;
  if (/^\s*#/.test(text) && text.indexOf('#') < i) return null;
  // a number: explain the option it belongs to
  for (const m of text.matchAll(/-?\d+(?:\.\d+)?/g)) {
    if (i >= m.index && i <= m.index + m[0].length) {
      const kw = text.slice(0, m.index).match(/(\w+)\s*=\s*[-(\[\s]*$/);
      const p = kw && PARAMS[kw[1]];
      if (!p) return null;
      return { from: line.from + m.index, to: line.from + m.index + m[0].length, ...tip(kw[1] + ' = ' + m[0], 'option', p[0], p[1]) };
    }
  }
  let s = i, e = i;
  while (s > 0 && /\w/.test(text[s - 1])) s--;
  while (e < text.length && /\w/.test(text[e])) e++;
  if (s === e || /\d/.test(text[s])) return null;
  const word = text.slice(s, e), before = text.slice(0, s), after = text.slice(e);
  const range = { from: line.from + s, to: line.from + e };
  const owner = (before.match(/(\w+)\s*\.\s*$/) || [])[1];
  const isKwarg = /^\s*=(?!=)/.test(after) && !owner;
  if (isKwarg && PARAMS[word]) return { ...range, ...tip(word, 'option', PARAMS[word][0], PARAMS[word][1]) };
  const docText = view.state.doc.toString();
  if (!owner && (word === 'def' || word === 'class') && /^\s*(def|class)\s/.test(text)) {
    const d = text.match(/(def|class)\s+(\w+)\s*\(([^)]*)\)/);
    if (d && word === 'def' && d[2] === 'construct') return { ...range, ...tip('def construct(self)', 'the recipe', 'This is the recipe of your video. Manimo runs every line indented under it, from top to bottom, to make the video.', 'Add steps inside it, indented four spaces. Rearranging the lines changes the order things happen.', 'self is the scene. Every scene needs exactly one construct.') };
    if (d && word === 'def') return { ...range, ...tip('def ' + d[2] + '(' + d[3] + ')', 'your function', 'You are defining your own helper called ' + d[2] + '. Everything indented under it runs each time you write ' + d[2] + '(…) elsewhere.', d[3].trim() ? 'The names in the brackets (' + d[3].trim() + ') are the values you hand it when you call it.' : 'It takes no values. Add some inside the brackets to make it flexible.', 'Use return to give something back to the caller.') };
    if (d && word === 'class') {
      const isScene = /Scene/.test(d[3]);
      return { ...range, ...tip('class ' + d[2] + '(' + d[3] + ')', isScene ? 'a scene' : 'a class', isScene ? d[2] + ' is one video. It shows in the Scene picker and is rendered on its own. m.Scene (in the brackets) says it is a ManimGX scene.' : 'A class named ' + d[2] + ', built on ' + (d[3] || 'nothing else') + '.', isScene ? 'Rename it to rename the video. Put the steps in its construct method.' : 'The indented lines below define what it can do.') };
    }
  }
  if (!owner && KEYWORDS[word]) return { ...range, ...tip(word, 'keyword', KEYWORDS[word][0], KEYWORDS[word][1], KEYWORDS[word][2]) };
  if (!owner && !BY_NAME[word] && !NAMES[word]) {
    // names you wrote yourself: your functions, scenes and variables
    const lines = docText.split('\n');
    const defAt = lines.findIndex((l) => new RegExp('^\\s*def\\s+' + word + '\\b').test(l));
    if (defAt >= 0) {
      const sig = lines[defAt].match(/def\s+\w+\s*\(([^)]*)\)/);
      const uses = (docText.match(new RegExp('\\b' + word + '\\s*\\(', 'g')) || []).length - 1;
      return { ...range, ...tip(word, 'your function', 'A helper you wrote on line ' + (defAt + 1) + '. Writing ' + word + '(…) runs the steps indented under it.', sig && sig[1].trim() ? 'It takes: ' + sig[1].trim() + '. Change what you pass in where you call it.' : 'Change the steps under line ' + (defAt + 1) + ' to change what it does everywhere.', uses > 0 ? 'Used ' + uses + ' time' + (uses === 1 ? '' : 's') + ' in this file.' : 'Not used yet.') };
    }
    const clsAt = lines.findIndex((l) => new RegExp('^\\s*class\\s+' + word + '\\b').test(l));
    if (clsAt >= 0) return { ...range, ...tip(word, /Scene/.test(lines[clsAt]) ? 'your scene' : 'your class', /Scene/.test(lines[clsAt]) ? 'One video. It appears in the Scene picker under this name.' : 'A kind of object you defined on line ' + (clsAt + 1) + '.', 'Rename it to rename the video.') };
    const varAt = lines.findIndex((l) => new RegExp('^\\s*' + word + '\\s*=(?!=)\\s*\\S').test(l));
    if (varAt >= 0 && !/^\s*(def|class|import|from)\b/.test(lines[varAt])) {
      const rhs = lines[varAt].replace(/^[^=]*=\s*/, '').trim();
      return { ...range, ...tip(word, 'your name', 'A name you chose. Line ' + (varAt + 1) + ' sets it to ' + (rhs.length > 70 ? rhs.slice(0, 70) + '…' : rhs) + '.', 'Change the right-hand side on line ' + (varAt + 1) + ' to change it everywhere ' + word + ' is used.') };
    }
  }
  const entry = BY_NAME[word];
  const own = NAMES[word];
  if (!entry && !own) return null;
  if (owner && owner !== 'self' && !aliases(view.state.doc.toString()).has(owner) && TOP_NAMES.has(word) && !(entry && entry.k === 'method') && !own) return null;
  const doc = entry && entry.d ? entry.d.replace(/\s+\S*$/, entry.d.length >= 79 ? '…' : '') : '';
  const what = own ? own[0] : doc || 'Part of ManimGX.';
  const params = entry ? paramNames(entry.s).slice(0, 7) : [];
  const extra = params.length ? 'Options you can set: ' + params.join(', ') + (paramNames(entry.s).length > 7 ? ', …' : '') : '';
  return { ...range, ...tip(word, (entry && KIND_LABEL[entry.k]) || '', what, own ? own[1] : '', extra) };
}
const hover = hoverTooltip((view, pos) => {
  const r = explainAt(view, pos);
  return r && { pos: r.from, end: r.to, above: false, create: () => ({ dom: r.dom }) };
}, { hoverTime: 350 });

/* ---------- the editor ---------- */
const External = Annotation.define();

export function create({ parent, doc = '', onChange, onCursor, onSave, onRun, onOpen }) {
  const run = (fn) => () => { if (fn) fn(); return true; };
  const view = new EditorView({
    parent,
    state: EditorState.create({
      doc,
      extensions: [
        lineNumbers(), marksField, flashField,
        highlightActiveLineGutter(), highlightSpecialChars(), history(), drawSelection(), dropCursor(),
        EditorState.allowMultipleSelections.of(true), indentUnit.of('    '),
        indentOnInput(), bracketMatching(), closeBrackets(), highlightActiveLine(), highlightSelectionMatches(),
        python(), hover,
        EditorState.languageData.of(() => [{ autocomplete: manimgxSource }]),
        autocompletion({ activateOnTyping: true, defaultKeymap: true, maxRenderedOptions: 60, icons: true }),
        syntaxHighlighting(style), theme,
        keymap.of([
          { key: 'Mod-s', run: run(onSave), preventDefault: true },
          { key: 'Mod-Enter', run: run(onRun), preventDefault: true },
          { key: 'Mod-o', run: run(onOpen), preventDefault: true },
          { key: 'Mod-h', run: openSearchPanel, preventDefault: true },
          ...closeBracketsKeymap, ...completionKeymap, ...searchKeymap, ...historyKeymap, ...defaultKeymap, indentWithTab,
        ]),
        EditorView.contentAttributes.of({ 'aria-label': 'ManimGX Python code', spellcheck: 'false', autocapitalize: 'off', autocorrect: 'off' }),
        EditorView.updateListener.of((u) => {
          if (u.docChanged && onChange && !u.transactions.some((tr) => tr.annotation(External))) onChange();
          if ((u.selectionSet || u.docChanged) && onCursor) {
            const head = u.state.selection.main.head, line = u.state.doc.lineAt(head);
            onCursor(line.number, head - line.from + 1);
          }
        }),
      ],
    }),
  });
  return {
    view,
    getValue: () => view.state.doc.toString(),
    setValue(text) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text }, selection: { anchor: 0 }, annotations: External.of(true),
                      effects: [setMarksEffect.of({}), flashEffect.of(null)], scrollIntoView: true });
      view.scrollDOM.scrollTop = 0; view.scrollDOM.scrollLeft = 0;
    },
    focus: () => view.focus(),
    /* the selected text, and an undoable whole-document replacement (used when the assistant's code is applied) */
    selection() { const s = view.state.selection.main; return view.state.sliceDoc(s.from, s.to); },
    replace(text) { view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text }, selection: { anchor: 0 }, userEvent: 'input.replace', scrollIntoView: true }); view.scrollDOM.scrollTop = 0; },
    /* menu commands: 'undo' | 'redo' | 'selectAll' | 'find' | 'cut' | 'copy' | 'paste' */
    run(name) {
      view.focus();
      if (name === 'undo') undo(view);
      else if (name === 'redo') redo(view);
      else if (name === 'selectAll') selectAll(view);
      else if (name === 'find') openSearchPanel(view);
      else if (name === 'cut' || name === 'copy') document.execCommand(name);
      else if (name === 'paste' && navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then((text) => { if (text) view.dispatch(view.state.replaceSelection(text), { userEvent: 'input.paste', scrollIntoView: true }); }).catch(() => {});
      }
    },
    canUndo: () => undoDepth(view.state) > 0,
    canRedo: () => redoDepth(view.state) > 0,
    lineCount: () => view.state.doc.lines,
    setMarks: (map) => view.dispatch({ effects: setMarksEffect.of(map || {}), annotations: External.of(true) }),
    clearMarks: () => view.dispatch({ effects: setMarksEffect.of({}), annotations: External.of(true) }),
    jump(n) {
      const doc = view.state.doc;
      if (!(n >= 1 && n <= doc.lines)) return;
      const line = doc.line(n);
      view.dispatch({ selection: { anchor: line.from, head: line.to }, effects: [EditorView.scrollIntoView(line.from, { y: 'center' }), flashEffect.of(null)], annotations: External.of(true) });
      setTimeout(() => view.dispatch({ effects: flashEffect.of(n), annotations: External.of(true) }), 30);   // restarts the animation if the same line is jumped to twice
      setTimeout(() => view.dispatch({ effects: flashEffect.of(null), annotations: External.of(true) }), 1600);
      view.focus();
    },
  };
}
export const apiVersion = names.version;
