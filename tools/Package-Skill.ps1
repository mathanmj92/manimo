<#
  Builds skills\manimo-animator\ : the same guide the in-app assistant uses, packaged as a Claude Code skill.
  Copy that folder into a project's .claude\skills\ (or ~\.claude\skills\) and Claude Code can write explainer-quality
  ManimGX / Manim scenes and check them with `manimgx inspect`.

  Source of truth: app\ai\skill\  (style_guide.md, manimgx.md, manim_ce.md, examples\) and app\ai\names.json.
#>
$root = Split-Path $PSScriptRoot -Parent
$src  = Join-Path $root 'app\ai\skill'
$out  = Join-Path $root 'skills\manimo-animator'
Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "$out\references", "$out\examples" | Out-Null

Copy-Item "$src\style_guide.md" "$out\references\style-guide.md"
Copy-Item "$src\manimgx.md"     "$out\references\manimgx-rules.md"
Copy-Item "$src\manim_ce.md"    "$out\references\manim-ce-rules.md"
Copy-Item "$src\examples\*.py"  "$out\examples\"

# the list of real ManimGX names, readable
$names = Get-Content (Join-Path $root 'app\ai\names.json') -Raw | ConvertFrom-Json
$groups = @{}
foreach ($item in $names.top) { $n, $k = $item -split ':', 2; if (-not $groups.ContainsKey($k)) { $groups[$k] = @() }; $groups[$k] += $n }
$md = "# Valid ManimGX names (version $($names.version))`n`nUse only these after ``m.```n`n"
foreach ($k in 'class', 'function', 'constant', 'variable') { if ($groups[$k]) { $md += "## $k`n$($groups[$k] -join ', ')`n`n" } }
$md += "## Scene methods`n$($names.scene -join ', ')`n"
Set-Content "$out\references\valid-names.md" $md -Encoding UTF8

$skill = @'
---
name: manimo-animator
description: Write explainer-quality math and science animations in ManimGX (import manimgx as m) or Manim Community Edition, in the style of 3Blue1Brown-type channels, then check them for errors and layout problems. Use when the user asks for an animation, a visual explanation, a Manim or ManimGX scene, or wants an existing scene fixed or improved.
---

# Manimo animator

You write complete, runnable Python files that teach one idea visually. The picture explains; words only name what is visible.

## Workflow
1. Decide the engine: code that starts with `import manimgx as m` is ManimGX; `from manim import *` is Manim Community Edition. If the user does not say, use ManimGX.
2. Read `references/style-guide.md` and the rules for the engine (`references/manimgx-rules.md` or `references/manim-ce-rules.md`). For ManimGX also keep `references/valid-names.md` open and use only names from it.
3. Look at the closest file in `examples/` for structure, pacing and layout before you write.
4. Write the full scene file: docstring with the one idea, palette constants, helpers, one scene class, one commented beat per `self.next_section(...)`.
5. **Check it.** For ManimGX run `manimgx inspect scene.py SceneName` (it prints errors with the line, and layout problems such as overlapping text or content outside the frame, and writes a storyboard PNG you can look at). Fix every problem, change only what is needed, and run it again until it prints "layout: no problems". For Manim CE render once with `manim render -ql scene.py SceneName`.
6. Reply with a 2 to 4 sentence plan, the file, and one to three short tweak suggestions.

## Safety
Animation code must not read or write files, use the network, run subprocesses or call `eval`/`exec`. Do not import anything except manimgx, manim, numpy, math, random and similar plain libraries.
'@
Set-Content "$out\SKILL.md" $skill -Encoding UTF8
Get-ChildItem $out -Recurse -File | ForEach-Object { $_.FullName.Replace("$out\", '') }
