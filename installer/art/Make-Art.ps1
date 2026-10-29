<#
  Draws every image the installer and the app icon need, from code (no external art, no fonts to license beyond Segoe UI
  which ships with Windows). Output goes next to this script:
    manimo.ico                         multi-size app icon (16 to 256)
    wizard-large-{164,246,328}.bmp     the tall picture on the Welcome and Finish pages
    wizard-small-{55,83,110}.bmp       the small logo in the page headers
    preview.png                        the three pieces side by side, for a quick look
#>
Add-Type -AssemblyName System.Drawing
$out = $PSScriptRoot

$NAVY  = [Drawing.Color]::FromArgb(11, 16, 48)
$INDIGO = [Drawing.Color]::FromArgb(30, 48, 142)
$ACCENT = [Drawing.Color]::FromArgb(76, 111, 255)
$ACCENT2 = [Drawing.Color]::FromArgb(47, 73, 201)
$CYAN  = [Drawing.Color]::FromArgb(92, 200, 255)
$AMBER = [Drawing.Color]::FromArgb(255, 200, 87)

function New-Canvas([int]$w, [int]$h) {
    $bmp = New-Object Drawing.Bitmap $w, $h, ([Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'; $g.TextRenderingHint = 'AntiAliasGridFit'; $g.InterpolationMode = 'HighQualityBicubic'; $g.PixelOffsetMode = 'HighQuality'
    return @{ Bmp = $bmp; G = $g }
}
function Rounded([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $p = New-Object Drawing.Drawing2D.GraphicsPath; $d = $r * 2
    $p.AddArc($x, $y, $d, $d, 180, 90); $p.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $p.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90); $p.AddArc($x, $y + $h - $d, $d, $d, 90, 90); $p.CloseFigure(); return $p
}
function Wave([float]$x0, [float]$x1, [float]$cy, [float]$amp, [float]$period, [float]$phase) {
    $pts = New-Object 'System.Collections.Generic.List[Drawing.PointF]'
    for ($x = $x0; $x -le $x1; $x += 2) { $pts.Add((New-Object Drawing.PointF $x, ($cy + $amp * [math]::Sin(($x / $period) * 2 * [math]::PI + $phase)))) }
    return $pts.ToArray()
}

# The brand mark: rounded square, one clean wave, one dot (the point that "draws" the wave).
function Draw-Mark($g, [float]$x, [float]$y, [float]$size) {
    $r = $size * 0.28
    $path = Rounded $x $y $size $size $r
    $grad = New-Object Drawing.Drawing2D.LinearGradientBrush ((New-Object Drawing.PointF $x, $y), (New-Object Drawing.PointF ($x + $size), ($y + $size)), $ACCENT, $ACCENT2)
    $g.FillPath($grad, $path)
    $k = $size / 32.0
    $pen = New-Object Drawing.Pen ([Drawing.Color]::White), (2.4 * $k); $pen.StartCap = 'Round'; $pen.EndCap = 'Round'; $pen.LineJoin = 'Round'
    $pts = Wave ($x + 5.5 * $k) ($x + 24.5 * $k) ($y + 16 * $k) (4.6 * $k) (13 * $k) ([math]::PI)
    $g.DrawCurve($pen, $pts, 0.5)
    $g.FillEllipse([Drawing.Brushes]::White, $x + 23.3 * $k, $y + 9.3 * $k, 4.4 * $k, 4.4 * $k)
}

function Draw-Side([int]$w) {
    $s = $w / 164.0; $h = [int](314 * $s)
    $c = New-Canvas $w $h; $g = $c.G
    $bg = New-Object Drawing.Drawing2D.LinearGradientBrush ((New-Object Drawing.Rectangle 0, 0, $w, $h), $NAVY, $INDIGO, 62.0)
    $g.FillRectangle($bg, 0, 0, $w, $h)
    # soft glow, lower right
    $gp = New-Object Drawing.Drawing2D.GraphicsPath; $gp.AddEllipse(-$w * 0.2, $h * 0.42, $w * 1.5, $h * 0.62)
    $pg = New-Object Drawing.Drawing2D.PathGradientBrush $gp
    $pg.CenterColor = [Drawing.Color]::FromArgb(110, $CYAN); $pg.SurroundColors = [Drawing.Color[]]@([Drawing.Color]::FromArgb(0, $CYAN))
    $g.FillPath($pg, $gp)
    # dot grid
    $dotBrush = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(26, 255, 255, 255)); $step = 14 * $s
    for ($yy = $step; $yy -lt $h; $yy += $step) { for ($xx = $step; $xx -lt $w; $xx += $step) { $g.FillEllipse($dotBrush, $xx - 0.9 * $s, $yy - 0.9 * $s, 1.8 * $s, 1.8 * $s) } }
    # flowing waves
    $cy = $h * 0.56
    $specs = @(
        @{ amp = 22; per = 74; ph = 0.2;  col = [Drawing.Color]::FromArgb(70, 255, 255, 255); wd = 1.6 },
        @{ amp = 30; per = 92; ph = 1.7;  col = [Drawing.Color]::FromArgb(130, $CYAN); wd = 2.0 },
        @{ amp = 26; per = 66; ph = 3.4;  col = [Drawing.Color]::FromArgb(235, $CYAN); wd = 2.8 })
    foreach ($sp in $specs) {
        $pen = New-Object Drawing.Pen $sp.col, ($sp.wd * $s); $pen.StartCap = 'Round'; $pen.EndCap = 'Round'
        $g.DrawCurve($pen, (Wave (-4 * $s) ($w + 4 * $s) $cy ($sp.amp * $s) ($sp.per * $s) $sp.ph), 0.5)
    }
    # the point drawing the front wave
    $px = $w * 0.78; $py = $cy + 26 * $s * [math]::Sin(($px / (66 * $s)) * 2 * [math]::PI + 3.4)
    $glow = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(70, $AMBER)); $g.FillEllipse($glow, $px - 11 * $s, $py - 11 * $s, 22 * $s, 22 * $s)
    $g.FillEllipse((New-Object Drawing.SolidBrush $AMBER), $px - 4.6 * $s, $py - 4.6 * $s, 9.2 * $s, 9.2 * $s)
    # brand
    Draw-Mark $g (20 * $s) (24 * $s) (40 * $s)
    $f1 = New-Object Drawing.Font('Segoe UI Semibold', (23 * $s), [Drawing.FontStyle]::Regular, [Drawing.GraphicsUnit]::Pixel)
    $g.DrawString('Manimo', $f1, [Drawing.Brushes]::White, (18 * $s), (72 * $s))
    $f2 = New-Object Drawing.Font('Segoe UI', (12.5 * $s), [Drawing.FontStyle]::Regular, [Drawing.GraphicsUnit]::Pixel)
    $g.DrawString("Math, in motion.", $f2, (New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(215, 255, 255, 255))), (20 * $s), (104 * $s))
    # footer pill
    $f3 = New-Object Drawing.Font('Segoe UI Semibold', (10.5 * $s), [Drawing.FontStyle]::Regular, [Drawing.GraphicsUnit]::Pixel)
    $txt = 'No Python required'; $sz = $g.MeasureString($txt, $f3)
    $pw = $sz.Width + 22 * $s; $ph = 24 * $s; $pxx = 20 * $s; $pyy = $h - 46 * $s
    $pill = Rounded $pxx $pyy $pw $ph ($ph / 2)
    $g.FillPath((New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(40, 255, 255, 255))), $pill)
    $g.DrawPath((New-Object Drawing.Pen ([Drawing.Color]::FromArgb(110, $CYAN)), (1 * $s)), $pill)
    $g.DrawString($txt, $f3, (New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(235, 255, 255, 255))), ($pxx + 11 * $s), ($pyy + 5.5 * $s))
    $g.Dispose(); return $c.Bmp
}

function Draw-Small([int]$px) {
    $c = New-Canvas $px $px; $g = $c.G; $g.Clear([Drawing.Color]::White)
    $m = $px * 0.06; Draw-Mark $g $m $m ($px - 2 * $m); $g.Dispose(); return $c.Bmp
}

function Save-Bmp24($bmp, [string]$path) {
    $flat = New-Object Drawing.Bitmap $bmp.Width, $bmp.Height, ([Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $g = [Drawing.Graphics]::FromImage($flat); $g.Clear([Drawing.Color]::White); $g.DrawImage($bmp, 0, 0, $bmp.Width, $bmp.Height); $g.Dispose()
    $flat.Save($path, [Drawing.Imaging.ImageFormat]::Bmp); $flat.Dispose()
}

function Write-Ico([string]$path, [int[]]$sizes) {
    $images = foreach ($sz in $sizes) {
        $c = New-Canvas $sz $sz; $g = $c.G; Draw-Mark $g 0 0 $sz; $g.Dispose()
        $ms = New-Object IO.MemoryStream; $c.Bmp.Save($ms, [Drawing.Imaging.ImageFormat]::Png); ,@($sz, $ms.ToArray())
    }
    $fs = [IO.File]::Create($path); $w = New-Object IO.BinaryWriter($fs)
    $w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]$images.Count)
    $offset = 6 + 16 * $images.Count
    foreach ($im in $images) {
        $dim = if ($im[0] -ge 256) { 0 } else { $im[0] }
        $w.Write([byte]$dim); $w.Write([byte]$dim); $w.Write([byte]0); $w.Write([byte]0)
        $w.Write([uint16]1); $w.Write([uint16]32); $w.Write([uint32]$im[1].Length); $w.Write([uint32]$offset)
        $offset += $im[1].Length
    }
    foreach ($im in $images) { $w.Write($im[1]) }
    $w.Close()
}

Write-Ico (Join-Path $out 'manimo.ico') @(16, 24, 32, 48, 64, 128, 256)
foreach ($w in 164, 246, 328) { $b = Draw-Side $w; Save-Bmp24 $b (Join-Path $out "wizard-large-$w.bmp"); if ($w -eq 328) { $big = $b } else { $b.Dispose() } }
foreach ($p in 55, 83, 110) { $b = Draw-Small $p; Save-Bmp24 $b (Join-Path $out "wizard-small-$p.bmp"); $b.Dispose() }

# preview sheet
$sheet = New-Object Drawing.Bitmap 760, 660; $g = [Drawing.Graphics]::FromImage($sheet); $g.Clear([Drawing.Color]::FromArgb(238, 238, 242))
$g.InterpolationMode = 'HighQualityBicubic'; $g.DrawImage($big, 20, 16, 328 * 1.0, 628 * 1.0)
$ic = New-Canvas 256 256; Draw-Mark $ic.G 0 0 256; $g.DrawImage($ic.Bmp, 400, 16, 256, 256)
$sm = Draw-Small 110; $g.DrawImage($sm, 400, 300, 110, 110); $g.Dispose()
$sheet.Save((Join-Path $out 'preview.png'), [Drawing.Imaging.ImageFormat]::Png)
Get-ChildItem $out -File | ForEach-Object { '{0,-26} {1,8:N0} bytes' -f $_.Name, $_.Length }
