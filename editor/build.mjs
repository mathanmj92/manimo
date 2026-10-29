import { build } from 'esbuild';
import { statSync } from 'node:fs';

await build({
  entryPoints: ['src/editor.js'],
  bundle: true,
  minify: true,
  format: 'iife',
  globalName: 'MGXEditor',
  target: 'es2020',
  outfile: '../app/vendor/editor.js',
  legalComments: 'none',
  loader: { '.json': 'json' },
});
console.log('built app/vendor/editor.js', (statSync('../app/vendor/editor.js').size / 1024).toFixed(0) + ' KB');
