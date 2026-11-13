"""A minimal PowerPoint (.pptx) writer using only the standard library: 16:9 slides with a title, text, pictures, speaker notes and a footer.
A .pptx is a zip of XML parts, so no extra library is needed. Slides are described as dicts (see `build`)."""
import struct
import zipfile
from xml.sax.saxutils import escape

W, H = 12192000, 6858000                 # a 16:9 slide in EMU (914400 to the inch)
MARGIN = 457200
NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
FONT = "Segoe UI"


def jpeg_size(data):
    """(width, height) of a JPEG, read from its header; None when it is not one."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def _run(text, size, color="1C2333", bold=False):
    return (f'<a:r><a:rPr lang="en-US" sz="{int(size * 100)}" b="{1 if bold else 0}" dirty="0"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>')


def _para(runs, align="l", space_after=0):
    return f'<a:p><a:pPr algn="{align}"><a:spcAft><a:spcPts val="{int(space_after * 100)}"/></a:spcAft></a:pPr>{runs}</a:p>'


def _box(sid, name, x, y, cx, cy, paras, anchor="t"):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{escape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="{anchor}"><a:normAutofit/></a:bodyPr><a:lstStyle/>{"".join(paras)}</p:txBody></p:sp>')


def _pic(sid, name, descr, rid, x, y, cx, cy):
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="{escape(name)}" descr="{escape(descr, {chr(34): "&quot;"})}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:ln w="9525"><a:solidFill><a:srgbClr val="C9CFDC"/></a:solidFill></a:ln></p:spPr></p:pic>')


def _fit(size, box_w, box_h):
    if not size:
        return box_w, box_h
    w, h = size
    s = min(box_w / w, box_h / h)
    return int(w * s), int(h * s)


def _slide_xml(shapes):
    return (XML + f'<p:sld {NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            + "".join(shapes) + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


def _notes_xml(text):
    paras = "".join(f'<a:p><a:r><a:rPr lang="en-US" dirty="0"/><a:t>{escape(t)}</a:t></a:r></a:p>' for t in (text.split("\n") if text else [""]))
    return (XML + f'<p:notes {NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
            '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
            f'<p:txBody><a:bodyPr/><a:lstStyle/>{paras}</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>')


def _rels(items):
    return (XML + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
            "".join(f'<Relationship Id="{i}" Type="http://schemas.openxmlformats.org/{t}" Target="{target}"/>' for i, t, target in items) + "</Relationships>")


R_OFFICE = "officeDocument/2006/relationships"          # the start of every relationship type's address, after http://schemas.openxmlformats.org/
THEME = (XML + '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Manimo"><a:themeElements>'
         '<a:clrScheme name="Manimo"><a:dk1><a:srgbClr val="1C2333"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="44506A"/></a:dk2><a:lt2><a:srgbClr val="F4F7FB"/></a:lt2>'
         '<a:accent1><a:srgbClr val="167688"/></a:accent1><a:accent2><a:srgbClr val="C2410C"/></a:accent2><a:accent3><a:srgbClr val="2F855A"/></a:accent3><a:accent4><a:srgbClr val="B45309"/></a:accent4>'
         '<a:accent5><a:srgbClr val="1E3A8A"/></a:accent5><a:accent6><a:srgbClr val="6B21A8"/></a:accent6><a:hlink><a:srgbClr val="07657E"/></a:hlink><a:folHlink><a:srgbClr val="6B21A8"/></a:folHlink></a:clrScheme>'
         f'<a:fontScheme name="Manimo"><a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
         '<a:fmtScheme name="Manimo"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
         '<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
         '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
         '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>'
         '</a:themeElements></a:theme>')
_LVL = '<a:lvl1pPr algn="l" defTabSz="914400" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1"><a:defRPr sz="2400" kern="1200"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr>'
MASTER = (XML + f'<p:sldMaster {NS}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
          '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>'
          '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
          '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
          f'<p:txStyles><p:titleStyle>{_LVL}</p:titleStyle><p:bodyStyle>{_LVL}</p:bodyStyle><p:otherStyle>{_LVL}</p:otherStyle></p:txStyles></p:sldMaster>')
LAYOUT = (XML + f'<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
          '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>'
          '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
NOTES_MASTER = (XML + f'<p:notesMaster {NS}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
                '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg" idx="2"/></p:nvPr></p:nvSpPr>'
                '<p:spPr><a:xfrm><a:off x="685800" y="1143000"/><a:ext cx="5486400" cy="3086100"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln w="12700"><a:solidFill><a:prstClr val="black"/></a:solidFill></a:ln></p:spPr></p:sp>'
                '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" sz="quarter" idx="3"/></p:nvPr></p:nvSpPr>'
                '<p:spPr><a:xfrm><a:off x="685800" y="4400550"/><a:ext cx="5486400" cy="3600450"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
                '<p:txBody><a:bodyPr vert="horz" lIns="91440" tIns="45720" rIns="91440" bIns="45720" rtlCol="0"/><a:lstStyle/><a:p><a:pPr lvl="0"/><a:r><a:rPr lang="en-US"/><a:t>Click to edit Master text styles</a:t></a:r></a:p></p:txBody></p:sp>'
                '</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
                '<p:notesStyle>' + _LVL.replace('sz="2400"', 'sz="1200"') + '</p:notesStyle></p:notesMaster>')


def build(path, deck):
    """deck: {title, footer, accent ('RRGGBB' for titles), slides: [slide]} where a slide is a dict:
       {"title": str, "paras": [(text, bold, color_or_None)], "image": jpeg bytes or None, "image_alt": str, "caption": str, "notes": str, "layout": "title"|"text"|"picture"|"textpicture"}."""
    accent = deck.get("accent", "167688")
    slides = deck["slides"]
    parts = {}
    types = [("/ppt/presentation.xml", "presentationml.presentation.main"), ("/ppt/slideMasters/slideMaster1.xml", "presentationml.slideMaster"),
             ("/ppt/slideLayouts/slideLayout1.xml", "presentationml.slideLayout"), ("/ppt/theme/theme1.xml", "theme"), ("/ppt/theme/theme2.xml", "theme"),
             ("/ppt/notesMasters/notesMaster1.xml", "presentationml.notesMaster"), ("/docProps/core.xml", None), ("/docProps/app.xml", None)]
    img_n = 0
    for n, s in enumerate(slides, 1):
        shapes, rels, sid = [], [("rId1", R_OFFICE + "/slideLayout", "../slideLayouts/slideLayout1.xml")], 2
        lay = s.get("layout", "text")
        if lay == "title":
            shapes.append(_box(sid, "Title", MARGIN, 2000000, W - 2 * MARGIN, 1500000, [_para(_run(s["title"], 44, accent, True))], "b")); sid += 1
            if s.get("caption"):
                shapes.append(_box(sid, "Subtitle", MARGIN, 3700000, W - 2 * MARGIN, 900000, [_para(_run(s["caption"], 24, "44506A"))])); sid += 1
        else:
            shapes.append(_box(sid, "Title", MARGIN, 280000, W - 2 * MARGIN, 700000, [_para(_run(s["title"], 32, accent, True))], "ctr")); sid += 1
            top, bottom = 1100000, 6250000
            if lay in ("picture", "textpicture") and s.get("image"):
                img_n += 1
                parts[f"/ppt/media/image{img_n}.jpg"] = s["image"]
                rels.append((f"rId{len(rels) + 1}", "officeDocument/2006/relationships/image", f"../media/image{img_n}.jpg"))
                if lay == "picture":
                    cap_h = 900000 if s.get("caption") else 0
                    cx, cy = _fit(jpeg_size(s["image"]), W - 2 * MARGIN, bottom - top - cap_h)
                    shapes.append(_pic(sid, "Picture", s.get("image_alt", ""), rels[-1][0], (W - cx) // 2, top, cx, cy)); sid += 1
                    if s.get("caption"):
                        shapes.append(_box(sid, "Caption", MARGIN, top + cy + 120000, W - 2 * MARGIN, bottom - top - cy - 120000 + 250000, [_para(_run(s["caption"], 24))])); sid += 1
                else:
                    cx, cy = _fit(jpeg_size(s["image"]), 5700000, bottom - top)
                    shapes.append(_pic(sid, "Picture", s.get("image_alt", ""), rels[-1][0], W - MARGIN - cx, top, cx, cy)); sid += 1
            if s.get("paras"):
                wide = W - 2 * MARGIN if lay in ("text",) else 5300000
                size = 24 if sum(len(p[0]) for p in s["paras"]) < 700 else 20
                ps = [_para(_run(t, size, c or "1C2333", b), space_after=8) for t, b, c in s["paras"]]
                shapes.append(_box(sid, "Text", MARGIN, top, wide, bottom - top, ps)); sid += 1
        shapes.append(_box(sid, "Footer", MARGIN, 6450000, 9000000, 280000, [_para(_run(deck.get("footer", ""), 11, "4D576B"))], "ctr"))
        rels.append((f"rId{len(rels) + 1}", "officeDocument/2006/relationships/notesSlide", f"../notesSlides/notesSlide{n}.xml"))
        parts[f"/ppt/slides/slide{n}.xml"] = _slide_xml(shapes)
        parts[f"/ppt/slides/_rels/slide{n}.xml.rels"] = _rels(rels)
        parts[f"/ppt/notesSlides/notesSlide{n}.xml"] = _notes_xml(s.get("notes", ""))
        parts[f"/ppt/notesSlides/_rels/notesSlide{n}.xml.rels"] = _rels([("rId1", "officeDocument/2006/relationships/notesMaster", "../notesMasters/notesMaster1.xml"),
                                                                       ("rId2", "officeDocument/2006/relationships/slide", f"../slides/slide{n}.xml")])
        types += [(f"/ppt/slides/slide{n}.xml", "presentationml.slide"), (f"/ppt/notesSlides/notesSlide{n}.xml", "presentationml.notesSlide")]
    ids = "".join(f'<p:sldId id="{255 + n}" r:id="rId{n + 3}"/>' for n in range(1, len(slides) + 1))
    parts["/ppt/presentation.xml"] = (XML + f'<p:presentation {NS} saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
                                      '<p:notesMasterIdLst><p:notesMasterId r:id="rId2"/></p:notesMasterIdLst>'
                                      f'<p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="{W}" cy="{H}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
    pres_rels = [("rId1", "officeDocument/2006/relationships/slideMaster", "slideMasters/slideMaster1.xml"), ("rId2", "officeDocument/2006/relationships/notesMaster", "notesMasters/notesMaster1.xml"),
                 ("rId3", "officeDocument/2006/relationships/theme", "theme/theme1.xml")] + [(f"rId{n + 3}", "officeDocument/2006/relationships/slide", f"slides/slide{n}.xml") for n in range(1, len(slides) + 1)]
    # slide ids use rId4.. so the theme (rId3) sits between the masters and the slides
    parts["/ppt/_rels/presentation.xml.rels"] = _rels(pres_rels)
    parts["/ppt/slideMasters/slideMaster1.xml"] = MASTER
    parts["/ppt/slideMasters/_rels/slideMaster1.xml.rels"] = _rels([("rId1", "officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"), ("rId2", "officeDocument/2006/relationships/theme", "../theme/theme1.xml")])
    parts["/ppt/slideLayouts/slideLayout1.xml"] = LAYOUT
    parts["/ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = _rels([("rId1", "officeDocument/2006/relationships/slideMaster", "../slideMasters/slideMaster1.xml")])
    parts["/ppt/theme/theme1.xml"] = THEME
    parts["/ppt/theme/theme2.xml"] = THEME
    parts["/ppt/notesMasters/notesMaster1.xml"] = NOTES_MASTER
    parts["/ppt/notesMasters/_rels/notesMaster1.xml.rels"] = _rels([("rId1", "officeDocument/2006/relationships/theme", "../theme/theme2.xml")])
    parts["/docProps/core.xml"] = (XML + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
                                   'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                                   f'<dc:title>{escape(deck.get("title", ""))}</dc:title><dc:creator>Manimo</dc:creator></cp:coreProperties>')
    parts["/docProps/app.xml"] = XML + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Manimo</Application></Properties>'
    root_rels = _rels([("rId1", "officeDocument/2006/relationships/officeDocument", "ppt/presentation.xml"),
                       ("rId2", "package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
                       ("rId3", "officeDocument/2006/relationships/extended-properties", "docProps/app.xml")])
    ct = (XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/><Default Extension="jpg" ContentType="image/jpeg"/>')
    for name, kind in types:
        if name == "/docProps/core.xml":
            ct += f'<Override PartName="{name}" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        elif name == "/docProps/app.xml":
            ct += f'<Override PartName="{name}" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        elif kind == "theme":
            ct += f'<Override PartName="{name}" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        else:
            ct += f'<Override PartName="{name}" ContentType="application/vnd.openxmlformats-officedocument.{kind}+xml"/>'
    ct += "</Types>"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        for name, data in parts.items():
            z.writestr(name.lstrip("/"), data)
    return len(slides)
