from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import os
from typing import List
from convert_bpmn import perform_conversion

app = FastAPI(title="BPMN Plus Converter")

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BPMN Plus | Premium Converter</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --card-bg: rgba(30, 41, 59, 0.7);
            --text: #f8fafc;
            --accent: #00d2ff;
            --success: #059669;
            --error: #dc2626;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Outfit', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .container {
            width: 90%;
            max-width: 800px;
            padding: 40px;
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            text-align: center;
        }

        h1 {
            font-size: 2.8rem;
            margin-bottom: 0.4rem;
            background: linear-gradient(to right, #6366f1, #00d2ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 600;
        }

        .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }

        .upload-area {
            border: 2px dashed rgba(99, 102, 241, 0.4);
            border-radius: 16px;
            padding: 50px 30px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            background: rgba(99, 102, 241, 0.03);
        }

        .upload-area:hover {
            border-color: var(--primary);
            background: rgba(99, 102, 241, 0.08);
            transform: translateY(-2px);
        }

        .upload-area.dragging {
            border-color: var(--accent);
            background: rgba(0, 210, 255, 0.1);
        }

        .icon { font-size: 48px; margin-bottom: 12px; display: block; }
        .upload-hint { color: #64748b; font-size: 0.9rem; }

        #file-input { display: none; }

        .btn {
            background: var(--primary);
            color: white;
            border: none;
            padding: 14px 36px;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.2s;
            box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.4);
            margin-top: 20px;
        }

        .btn:hover {
            background: var(--primary-hover);
            transform: translateY(-1px);
            box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.4);
        }

        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        .file-list {
            margin-top: 24px;
            text-align: left;
            max-height: 400px;
            overflow-y: auto;
        }

        .file-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 14px 18px;
            border-radius: 12px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            animation: slideIn 0.3s ease-out;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .file-item .name {
            font-size: 0.9rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 55%;
        }

        .file-item .actions { display: flex; align-items: center; gap: 10px; }

        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }

        .badge {
            font-size: 0.75rem;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 500;
        }

        .badge-waiting { background: #475569; }
        .badge-done { background: var(--success); }
        .badge-error { background: var(--error); }

        .dl-btn {
            background: var(--accent);
            color: #0f172a;
            border: none;
            padding: 6px 14px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.15s;
            text-decoration: none;
        }

        .dl-btn:hover { opacity: 0.85; transform: scale(1.02); }

        .dl-all-btn {
            display: none;
            background: linear-gradient(135deg, #059669, #10b981);
            margin-top: 16px;
        }

        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #475569; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>BPMN Plus</h1>
        <p class="subtitle">批量转换 BPMN 为 Camunda Cloud 标准格式</p>

        <div class="upload-area" id="drop-zone">
            <span class="icon">🚀</span>
            <div>拖拽 BPMN 文件到此处 或 点击上传</div>
            <div class="upload-hint">支持批量上传多个 .bpmn 文件</div>
            <input type="file" id="file-input" multiple accept=".bpmn">
        </div>

        <div class="file-list" id="file-list"></div>

        <button class="btn" id="convert-btn" disabled>开始转换</button>
        <button class="btn dl-all-btn" id="dl-all-btn">全部下载</button>
    </div>

    <script>
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const fileList = document.getElementById('file-list');
        const convertBtn = document.getElementById('convert-btn');
        const dlAllBtn = document.getElementById('dl-all-btn');
        let selectedFiles = [];
        let convertedResults = [];

        dropZone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => handleFiles(e.target.files);

        dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragging'); };
        dropZone.ondragleave = () => dropZone.classList.remove('dragging');
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragging');
            handleFiles(e.dataTransfer.files);
        };

        function handleFiles(files) {
            selectedFiles = Array.from(files).filter(f => f.name.endsWith('.bpmn'));
            convertedResults = [];
            fileList.innerHTML = '';
            selectedFiles.forEach((f, i) => {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.id = 'item-' + i;
                item.innerHTML = `
                    <span class="name">${f.name}</span>
                    <div class="actions">
                        <span class="badge badge-waiting">等待中</span>
                    </div>`;
                fileList.appendChild(item);
            });
            convertBtn.disabled = selectedFiles.length === 0;
            convertBtn.innerText = '开始转换';
            dlAllBtn.style.display = 'none';
        }

        convertBtn.onclick = async () => {
            const formData = new FormData();
            selectedFiles.forEach(f => formData.append('files', f));

            convertBtn.disabled = true;
            convertBtn.innerText = '转换中...';

            try {
                const res = await fetch('/convert', { method: 'POST', body: formData });
                const data = await res.json();

                if (res.ok) {
                    convertedResults = data.results;
                    data.results.forEach((r, i) => {
                        const item = document.getElementById('item-' + i);
                        if (!item) return;
                        const actions = item.querySelector('.actions');
                        if (r.success) {
                            const blob = new Blob([r.content], { type: 'application/xml' });
                            const url = URL.createObjectURL(blob);
                            actions.innerHTML = `
                                <span class="badge badge-done">完成</span>
                                <a class="dl-btn" href="${url}" download="${r.filename}">下载</a>`;
                        } else {
                            actions.innerHTML = `<span class="badge badge-error">失败</span>`;
                        }
                    });

                    const successCount = data.results.filter(r => r.success).length;
                    convertBtn.innerText = `转换完成 (${successCount}/${data.results.length})`;

                    if (successCount > 1) {
                        dlAllBtn.style.display = 'inline-block';
                    }
                } else {
                    alert(data.detail || '转换失败');
                    convertBtn.disabled = false;
                    convertBtn.innerText = '开始转换';
                }
            } catch (err) {
                console.error(err);
                alert('连接错误: ' + err.message);
                convertBtn.disabled = false;
                convertBtn.innerText = '开始转换';
            }
        };

        dlAllBtn.onclick = () => {
            convertedResults.forEach(r => {
                if (r.success) {
                    const blob = new Blob([r.content], { type: 'application/xml' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = r.filename;
                    a.click();
                }
            });
        };
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return HTML_CONTENT

@app.post("/convert")
async def batch_convert(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        content = await file.read()
        try:
            text_content = content.decode("utf-8")
            converted_xml = perform_conversion(text_content, file.filename)
            if converted_xml:
                new_name = f"{os.path.splitext(file.filename)[0]}_camunda.bpmn"
                results.append({"filename": new_name, "content": converted_xml, "success": True})
                print(f"✓ {file.filename}")
            else:
                results.append({"filename": file.filename, "content": "", "success": False})
                print(f"✗ {file.filename}: no processes found")
        except Exception as e:
            results.append({"filename": file.filename, "content": "", "success": False})
            print(f"✗ {file.filename}: {e}")
            import traceback
            traceback.print_exc()

    return JSONResponse({"results": results})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9998)
