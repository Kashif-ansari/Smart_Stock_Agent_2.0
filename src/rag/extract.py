from pathlib import Path
from io import BytesIO
import re
from src.services.data import read_file

def extract(name,raw):
    if len(raw)>10*1024**2:raise ValueError('Knowledge files must be smaller than 10 MB.')
    ext=Path(name).suffix.lower();segments=[]
    if ext=='.pdf':
        from pypdf import PdfReader
        pdf=PdfReader(BytesIO(raw))
        if pdf.is_encrypted:raise ValueError('Remove password protection before uploading.')
        if len(pdf.pages)>250:raise ValueError('Maximum 250 pages per file.')
        for i,page in enumerate(pdf.pages):
            value=page.extract_text(extraction_mode='layout') or ''
            if value.strip():segments.append({'location':f'Page {i+1}','text':value})
            else:
                if len(pdf.pages)>20:raise ValueError('PDFs needing OCR are limited to 20 pages. Split the file first.')
                try:
                    import fitz,pytesseract
                    from PIL import Image
                    with fitz.open(stream=raw,filetype='pdf') as scanned:
                        pix=scanned[i].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
                        if pix.width*pix.height>20_000_000:raise ValueError('Scanned page is too large.')
                        img=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
                        value=pytesseract.image_to_string(img,timeout=30)
                    if value.strip():segments.append({'location':f'Page {i+1}, OCR requiring review','text':value})
                except ImportError as exc:raise ValueError('Scanned pages require requirements-ocr.txt and Tesseract. Use an OCR text file instead.') from exc
    elif ext=='.docx':
        import zipfile
        with zipfile.ZipFile(BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist())>50*1024**2:raise ValueError('Document expands beyond safe limits.')
        from docx import Document
        d=Document(BytesIO(raw))
        heading='Document'
        from docx.text.paragraph import Paragraph
        table_number=0
        for item in d.iter_inner_content():
            if isinstance(item,Paragraph):
                if item.style.name.startswith('Heading'):heading=item.text
                if item.text.strip():segments.append({'location':heading,'text':item.text})
            else:
                table_number+=1
                headers=[c.text for c in item.rows[0].cells] if item.rows else []
                for j,row in enumerate(item.rows[1:],2):
                    segments.append({'location':f'{heading}, Table {table_number} row {j}','text':' | '.join(f'{h}: {c.text}' for h,c in zip(headers,row.cells))})
    elif ext in {'.csv','.tsv','.xlsx','.xls'}:
        first,sheets=read_file(name,raw)
        for sheet in sheets or [0]:
            df,_=read_file(name,raw,sheet)
            for i,row in df.fillna('').iterrows():
                segments.append({'location':f'Sheet {sheet} row {i+2}','text':' | '.join(f'{c}: {row[c]}' for c in df.columns)})
    elif ext in {'.txt','.md','.html','.htm'}:
        value=raw.decode('utf-8-sig',errors='replace')
        if ext in {'.html','.htm'}:
            from bs4 import BeautifulSoup
            soup=BeautifulSoup(value,'html.parser')
            for e in soup(['script','style','noscript','iframe']):e.decompose()
            value=soup.get_text('\n',strip=True)
        segments=[{'location':f'Section {i+1}','text':x} for i,x in enumerate(re.split(r'\n\s*\n',value)) if x.strip()]
    elif ext in {'.png','.jpg','.jpeg'}:
        try:
            import pytesseract
            from PIL import Image
            img=Image.open(BytesIO(raw))
            if img.width*img.height>20_000_000:raise ValueError('Image is too large.')
            value=pytesseract.image_to_string(img,timeout=30)
            segments=[{'location':'OCR text requiring review','text':value}]
        except ImportError as exc:raise ValueError('OCR requires pytesseract and the Tesseract executable. Use an extracted text file instead.') from exc
    else:raise ValueError('Unsupported knowledge file type.')
    if not segments or not any(s['text'].strip() for s in segments):raise ValueError('No readable text found. Review the scan or upload extracted text.')
    if sum(len(s['text']) for s in segments)>2_000_000:raise ValueError('Extracted text exceeds 2 million characters.')
    return segments

def chunk_segments(segments,words=220,overlap=35):
    if not 0<=overlap<words:raise ValueError('Chunk overlap must be smaller than the chunk size.')
    chunks=[];buffer=[];locations=[]
    def emit():
        if buffer:chunks.append({'text':' '.join(buffer),'location':', '.join(dict.fromkeys(locations))[:500]})
    for s in segments:
        tokens=s['text'].split()
        if buffer and len(buffer)+len(tokens)>words:
            emit();keep=min(overlap,max(0,words-len(tokens)))
            buffer=buffer[-keep:] if keep else [];locations=locations[-1:] if keep else []
        while len(tokens)>words:
            if buffer:emit();buffer=[];locations=[]
            chunks.append({'text':' '.join(tokens[:words]),'location':s['location']})
            tokens=tokens[words-overlap:]
        buffer.extend(tokens);locations.append(s['location'])
    emit()
    return chunks
