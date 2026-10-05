from io import BytesIO
import csv, json, re, math
from datetime import datetime
from html import escape
from sqlalchemy import select
from src.core.auth import require,allowed,audit
from src.core.db import session
from src.core.models import Report,now

def scope_allowed(ctx,scope):
    permissions={'general':'knowledge.read','sales':'sales.read','inventory':'inventory.read','finance':'finance.read','hr':'hr.read'}
    return scope in permissions and allowed(ctx,permissions[scope])

def json_safe(value):
    """Keep missing numeric values null across SQL JSON and all export formats."""
    if isinstance(value,dict):return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_safe(v) for v in value]
    if hasattr(value,'item'):return json_safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    if value is None or isinstance(value,(str,int,float,bool)):return value
    return str(value)

def build_report(title,summary,tables=None,sources=None,limitations=None,scope='general'):
    return json_safe({'title':title,'generated_at':now().isoformat()+'Z','summary':summary,'tables':tables or {},'sources':sources or [],'limitations':limitations or [],'scope':scope,'approval_status':'Advisory report; consequential actions need separate approval.'})

def save_report(ctx,payload):
    require(ctx,'reports.write')
    if not scope_allowed(ctx,payload.get('scope','general')):raise PermissionError('Report scope is restricted.')
    clean=json_safe(payload)
    with session() as s:
        r=Report(tenant_id=ctx.tenant_id,title=clean['title'][:200],scope=clean.get('scope','general'),payload=clean)
        s.add(r);s.flush();audit(s,ctx,'report.created',{'report_id':r.id,'scope':r.scope});return r.id

def reports(ctx):
    require(ctx,'reports.read')
    with session() as s:
        rows=s.scalars(select(Report).where(Report.tenant_id==ctx.tenant_id).order_by(Report.created_at.desc())).all()
    return [r for r in rows if scope_allowed(ctx,r.scope)]

def get_report(ctx,rid):
    require(ctx,'reports.read')
    with session() as s:r=s.scalar(select(Report).where(Report.tenant_id==ctx.tenant_id,Report.id==rid))
    if not r or not scope_allowed(ctx,r.scope):raise PermissionError('Report unavailable.')
    return r.payload

def safe_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')):return "'"+value
    return value

def export(payload,fmt):
    payload=json_safe(payload)
    out=BytesIO();tables=payload.get('tables',{})
    if fmt=='json':return json.dumps(payload,indent=2,default=str).encode()
    if fmt in {'txt','md'}:
        lines=[payload['title'],payload['generated_at'],payload['summary'],'']
        for title,rows in tables.items():
            lines.append(title)
            if rows:
                cols=list(rows[0]);lines.extend([' | '.join(cols),' | '.join(['---']*len(cols))]);lines.extend(' | '.join(str(r.get(c,'')) for c in cols) for r in rows)
        lines+=['Sources']+[str(x) for x in payload.get('sources',[])]+['Limitations']+payload.get('limitations',[])+[payload['approval_status']]
        return '\n'.join(lines).encode()
    if fmt=='csv':
        from io import StringIO
        s=StringIO();w=csv.writer(s)
        w.writerow(['Report',safe_cell(payload['title'])]);w.writerow(['Generated',payload['generated_at']])
        w.writerow(['Summary',safe_cell(payload['summary'])]);w.writerow(['Approval',payload['approval_status']])
        for title,rows in tables.items():
            w.writerow([]);w.writerow([safe_cell(title)])
            if rows:
                cols=list(rows[0]);w.writerow([safe_cell(c) for c in cols])
                for r in rows:w.writerow([safe_cell(r.get(c,'')) for c in cols])
        w.writerow([]);w.writerow(['Sources']);[w.writerow([safe_cell(str(x))]) for x in payload.get('sources',[])]
        w.writerow(['Limitations']);[w.writerow([safe_cell(str(x))]) for x in payload.get('limitations',[])]
        return s.getvalue().encode('utf-8-sig')
    if fmt=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font,PatternFill,Alignment
        wb=Workbook();ws=wb.active;ws.title='Report'
        for row in [['Title',payload['title']],['Generated',payload['generated_at']],['Summary',payload['summary']],['Approval',payload['approval_status']]]:ws.append([safe_cell(v) for v in row])
        for title,rows in tables.items():
            sheet=wb.create_sheet(re.sub(r'[\\/*?:\[\]]','',title)[:27] or 'Table')
            if rows:
                cols=list(rows[0]);sheet.append([safe_cell(c) for c in cols])
                for r in rows:sheet.append([safe_cell(r.get(c)) for c in cols])
        s=wb.create_sheet('Sources and notes')
        for x in payload.get('sources',[])+payload.get('limitations',[]):s.append([safe_cell(str(x))])
        for sheet in wb:
            sheet.freeze_panes='A2'
            for cell in sheet[1]:cell.fill=PatternFill('solid',fgColor='0F172A');cell.font=Font(color='FFFFFF',bold=True)
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width=min(55,max(16,max(len(str(c.value or '')) for c in col)+2))
            for row in sheet:
                for cell in row:cell.alignment=Alignment(vertical='top',wrap_text=True)
        wb.save(out)
    elif fmt=='docx':
        from docx import Document
        from docx.shared import Pt,Inches
        from docx.enum.section import WD_ORIENT
        from docx.oxml import OxmlElement
        d=Document();d.styles['Normal'].font.size=Pt(9)
        section=d.sections[0];section.orientation=WD_ORIENT.LANDSCAPE
        section.page_width=Inches(11);section.page_height=Inches(8.5)
        section.left_margin=section.right_margin=Inches(.6)
        d.add_heading(payload['title'],0);d.add_paragraph(payload['generated_at']);d.add_paragraph(payload['summary'])
        for title,rows in tables.items():
            d.add_heading(title,1)
            if rows:
                cols=list(rows[0])
                groups=[cols] if len(cols)<=6 else [[cols[0]]+cols[i:i+5] for i in range(1,len(cols),5)]
                for group in groups:
                    t=d.add_table(rows=1,cols=len(group));t.style='Light Shading Accent 1'
                    for c,k in zip(t.rows[0].cells,group):c.text=k
                    header=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(header)
                    for r in rows:
                        for c,k in zip(t.add_row().cells,group):c.text=str(r.get(k,''))
                    d.add_paragraph()
        for heading,values in [('Sources',payload.get('sources',[])),('Limitations',payload.get('limitations',[]))]:
            d.add_heading(heading,1)
            for value in values:d.add_paragraph(str(value))
        d.add_paragraph(payload['approval_status']);d.save(out)
    elif fmt=='pdf':
        from pathlib import Path
        import reportlab
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
        from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape,letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        fonts=Path(reportlab.__file__).parent/'fonts'
        if 'StockSans' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('StockSans',str(fonts/'Vera.ttf')))
            pdfmetrics.registerFont(TTFont('StockSansBold',str(fonts/'VeraBd.ttf')))
        styles=getSampleStyleSheet()
        for name in ['Normal','BodyText','Title','Heading2']:
            styles[name].fontName='StockSansBold' if name in {'Title','Heading2'} else 'StockSans'
        styles.add(ParagraphStyle('TableText',fontName='StockSans',fontSize=8,leading=11))
        story=[Paragraph(escape(payload['title']),styles['Title']),Paragraph(escape(payload['generated_at']),styles['Normal']),Spacer(1,10),Paragraph(escape(payload['summary']),styles['BodyText'])]
        for title,rows in tables.items():
            story.extend([Spacer(1,12),Paragraph(escape(title),styles['Heading2'])])
            if rows:
                cols=list(rows[0])
                # Wide data is split into labelled column groups, preserving row identity.
                groups=[cols] if len(cols)<=6 else [[cols[0]]+cols[i:i+5] for i in range(1,len(cols),5)]
                for group in groups:
                    cells=[[Paragraph(escape(str(c).replace('_',' ')),styles['TableText']) for c in group]]
                    cells.extend([[Paragraph(escape(str(r.get(c,''))),styles['TableText']) for c in group] for r in rows])
                    t=Table(cells,colWidths=[690/len(group)]*len(group),repeatRows=1)
                    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E2E8F0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
                    story.extend([t,Spacer(1,10)])
        for label,values in [('Sources',payload.get('sources',[])),('Limitations',payload.get('limitations',[]))]:
            story.append(Paragraph(label,styles['Heading2']))
            for v in values:story.append(Paragraph(escape(str(v)),styles['BodyText']))
        story.extend([Spacer(1,10),Paragraph(escape(payload['approval_status']),styles['BodyText'])])
        def footer(canvas,doc):
            canvas.setFont('StockSans',8);canvas.drawRightString(747,20,f'Smart Stock Agent | Page {doc.page}')
        SimpleDocTemplate(out,pagesize=landscape(letter),leftMargin=45,rightMargin=45,topMargin=36,bottomMargin=36).build(story,onFirstPage=footer,onLaterPages=footer)
    else:raise ValueError('Unsupported export format.')
    return out.getvalue()
