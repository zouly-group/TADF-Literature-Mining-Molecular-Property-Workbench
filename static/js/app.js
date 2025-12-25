// 全局状态
let currentPaperId = null;
let currentPaperData = null;
let currentDataType = 'photophysical';
let currentImageData = null;

// 数据库查看相关变量
let currentTable = null;
let currentPage = 1;
let currentSearch = '';
let tablePagination = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initFileUpload();
    initPasteArea();
    initImageUpload();
    loadPapers();
    loadExtractionConfigs();
    initConfigCustomFields();
    loadDatabaseTables();
    
    // 设置文件上传区域
    const fileUploadArea = document.getElementById('file-upload-area');
    const fileInput = document.getElementById('pdf-file');
    
    fileUploadArea.addEventListener('click', () => fileInput.click());
    fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileUploadArea.style.borderColor = '#2563eb';
    });
    fileUploadArea.addEventListener('dragleave', () => {
        fileUploadArea.style.borderColor = '#e5e7eb';
    });
    fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUploadArea.style.borderColor = '#e5e7eb';
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            updateFileUploadDisplay(e.dataTransfer.files[0].name);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            updateFileUploadDisplay(e.target.files[0].name);
        }
    });
});

// 初始化文件上传
function initFileUpload() {
    const form = document.getElementById('upload-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        const paperId = document.getElementById('paper-id').value;
        
        if (!paperId) {
            showToast('请输入论文ID', 'error');
            return;
        }
        
        const fileInput = document.getElementById('pdf-file');
        if (!fileInput.files || fileInput.files.length === 0) {
            showToast('请选择PDF文件', 'error');
            return;
        }
        
        formData.append('file', fileInput.files[0]);
        formData.append('paper_id', paperId);
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                showToast('上传成功，开始处理...', 'success');
                showProgress(result.status_key);
                pollStatus(result.status_key);
            } else {
                showToast(result.message || '上传失败', 'error');
            }
        } catch (error) {
            showToast('上传失败: ' + error.message, 'error');
        }
    });
}

// 更新文件上传显示
function updateFileUploadDisplay(filename) {
    const placeholder = document.querySelector('.file-upload-placeholder');
    if (placeholder) {
        placeholder.innerHTML = `<span class="upload-icon">📄</span><p>${filename}</p>`;
    }
}

// 显示进度
function showProgress(statusKey) {
    const container = document.getElementById('progress-container');
    container.classList.remove('hidden');
}

// 轮询状态
function pollStatus(statusKey) {
    let errorCount = 0;
    const maxErrors = 3;  // 最多允许3次404错误
    
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${statusKey}`);
            const result = await response.json();
            
            if (result.success) {
                errorCount = 0;  // 重置错误计数
                const status = result.status;
                
                // 更新进度条
                const progressFill = document.getElementById('progress-fill');
                const progressMessage = document.getElementById('progress-message');
                
                if (progressFill) {
                    progressFill.style.width = status.progress + '%';
                }
                if (progressMessage) {
                    progressMessage.textContent = status.message;
                }
                
                if (status.status === 'completed') {
                    clearInterval(interval);
                    showToast('处理完成！', 'success');
                    loadPapers();
                    showPage('papers');
                    
                    // 自动打开论文详情
                    if (status.result) {
                        setTimeout(() => {
                            openPaperModal(status.result.paper_id);
                        }, 500);
                    }
                } else if (status.status === 'error') {
                    clearInterval(interval);
                    showToast('处理失败: ' + status.message, 'error');
                } else if (status.status === 'expired') {
                    // 状态已过期（应用重启）
                    errorCount++;
                    if (errorCount >= maxErrors) {
                        clearInterval(interval);
                        showToast('状态已过期（可能因为应用重启），请刷新页面查看已处理的论文', 'warning');
                        loadPapers();  // 自动刷新论文列表
                    }
                }
            } else {
                // 处理失败的情况
                if (result.suggestion === 'refresh') {
                    errorCount++;
                    if (errorCount >= maxErrors) {
                        clearInterval(interval);
                        showToast(result.message || '状态已过期，请刷新页面查看已处理的论文', 'warning');
                        loadPapers();  // 刷新论文列表
                    }
                } else {
                    clearInterval(interval);
                    showToast(result.message || '获取状态失败', 'error');
                }
            }
        } catch (error) {
            errorCount++;
            if (errorCount >= maxErrors) {
                clearInterval(interval);
                console.error('轮询状态失败:', error);
                showToast('获取状态失败: ' + error.message, 'error');
            }
        }
    }, 2000); // 每2秒轮询一次
}

// 页面切换
function showPage(pageName) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(pageName + '-page').classList.add('active');
}

// 加载论文列表
async function loadPapers() {
    const listContainer = document.getElementById('papers-list');
    listContainer.innerHTML = '<p class="loading">加载中...</p>';
    
    try {
        const response = await fetch('/api/papers');
        const result = await response.json();
        
        if (result.success && result.papers.length > 0) {
            listContainer.innerHTML = '';
            result.papers.forEach(paper => {
                const item = createPaperItem(paper);
                listContainer.appendChild(item);
            });
        } else {
            listContainer.innerHTML = '<p class="loading">暂无论文，请上传PDF文件</p>';
        }
    } catch (error) {
        listContainer.innerHTML = '<p class="loading">加载失败: ' + error.message + '</p>';
    }
}

// 创建论文项
function createPaperItem(paper) {
    const item = document.createElement('div');
    item.className = 'paper-item';
    item.innerHTML = `
        <h3>${paper.paper_id}</h3>
        <p class="meta">
            <span>光物性数据: ${paper.photophysical_count}</span>
            <span>器件数据: ${paper.device_count}</span>
            <span>分子结构图: ${paper.molecular_figures_count}</span>
            <span>创建时间: ${formatDate(paper.created_at)}</span>
        </p>
    `;
    item.addEventListener('click', () => openPaperModal(paper.paper_id));
    return item;
}

// 打开论文详情弹窗
async function openPaperModal(paperId) {
    currentPaperId = paperId;
    const modal = document.getElementById('paper-modal');
    const title = document.getElementById('modal-title');
    
    // 清除旧数据，避免显示上次的内容
    currentPaperData = null;
    document.getElementById('data-table-head').innerHTML = '';
    document.getElementById('data-table-body').innerHTML = '<tr><td colspan="10" class="loading">加载中...</td></tr>';
    
    title.textContent = `论文: ${paperId}`;
    
    try {
        // 使用时间戳防止缓存
        const response = await fetch(`/api/papers/${paperId}?t=${Date.now()}`);
        const result = await response.json();
        
        if (result.success) {
            currentPaperData = result.data;
            // 重置数据类型
            currentDataType = 'photophysical';
            loadPaperData();
            loadPaperFigures();
            loadCompoundSelect();
            // 如果原文查看标签页是活动的，加载数据列表
            if (document.getElementById('source-tab')?.classList.contains('active')) {
                loadSourceDataList();
            }
            showModal('paper-modal');
        } else {
            showToast('加载论文数据失败', 'error');
        }
    } catch (error) {
        showToast('加载失败: ' + error.message, 'error');
    }
}

// 加载论文数据
function loadPaperData() {
    if (!currentPaperData) return;
    
    const data = currentPaperData[currentDataType + '_data'] || [];
    const tableHead = document.getElementById('data-table-head');
    const tableBody = document.getElementById('data-table-body');
    
    if (data.length === 0) {
        tableHead.innerHTML = '';
        tableBody.innerHTML = '<tr><td colspan="10" class="loading">暂无数据</td></tr>';
        return;
    }
    
    // 生成表头
    const headers = Object.keys(data[0]);
    tableHead.innerHTML = '<tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr>';
    
    // 生成表体
    tableBody.innerHTML = data.map((row, idx) => {
        return '<tr>' + headers.map(header => {
            const value = row[header] || '';
            if (header === 'smiles') {
                return `<td><textarea data-row="${idx}" data-field="${header}">${value}</textarea></td>`;
            } else if (typeof value === 'number') {
                return `<td><input type="number" data-row="${idx}" data-field="${header}" value="${value}"></td>`;
            } else {
                return `<td><input type="text" data-row="${idx}" data-field="${header}" value="${value}"></td>`;
            }
        }).join('') + '</tr>';
    }).join('');
    
    // 绑定输入事件
    tableBody.querySelectorAll('input, textarea').forEach(input => {
        input.addEventListener('change', updateDataCell);
    });
}

// 更新数据单元格
function updateDataCell(e) {
    const row = parseInt(e.target.dataset.row);
    const field = e.target.dataset.field;
    const value = e.target.value;
    
    if (currentPaperData && currentPaperData[currentDataType + '_data']) {
        currentPaperData[currentDataType + '_data'][row][field] = value;
    }
}

// 切换数据类型
function switchDataType(type) {
    currentDataType = type;
    
    // 更新按钮状态
    document.querySelectorAll('.tab-controls .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    loadPaperData();
}

// 保存数据
async function saveData() {
    if (!currentPaperId || !currentPaperData) {
        showToast('没有可保存的数据', 'error');
        return;
    }
    
    try {
        showToast('正在保存并同步到数据库...', 'success');
        
        const response = await fetch(`/api/papers/${currentPaperId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                photophysical_data: currentPaperData.photophysical_data,
                device_data: currentPaperData.device_data
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('保存成功，已同步到数据库', 'success');
        } else {
            showToast('保存失败: ' + result.message, 'error');
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
    }
}

// 导出数据
function exportData() {
    if (!currentPaperData) {
        showToast('没有可导出的数据', 'error');
        return;
    }
    
    const dataStr = JSON.stringify(currentPaperData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentPaperId}_extracted_data.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// 加载论文图片
function loadPaperFigures() {
    const container = document.getElementById('figures-container');
    
    if (!currentPaperData || !currentPaperData.molecular_figures) {
        container.innerHTML = '<p class="loading">暂无分子结构图</p>';
        return;
    }
    
    const figures = currentPaperData.molecular_figures;
    
    if (figures.length === 0) {
        container.innerHTML = '<p class="loading">暂无分子结构图</p>';
        return;
    }
    
    container.innerHTML = figures.map(fig => {
        // 使用文件名而不是完整路径，避免路径编码问题
        const imagePath = fig.image_path || '';
        const imageName = imagePath.split('/').pop() || imagePath;
        // 如果路径是绝对路径，只传递文件名；否则传递相对路径
        const pathToUse = imagePath.startsWith('/') ? imageName : imagePath;
        return `
        <div class="figure-item" onclick="viewFigure('${fig.image_path}')">
            <img src="/api/images/${currentPaperId}/${encodeURIComponent(pathToUse)}" alt="${fig.figure_id}" onerror="this.onerror=null; this.src='/api/images/${currentPaperId}/${encodeURIComponent(imageName)}';">
            <div class="caption">${fig.caption ? fig.caption.substring(0, 100) : fig.figure_id}</div>
        </div>
    `;
    }).join('');
}

// 查看图片
function viewFigure(imagePath) {
    // 可以在这里实现图片查看功能
    window.open(`/api/images/${currentPaperId}/${encodeURIComponent(imagePath)}`, '_blank');
}

// 标签页切换
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.getElementById(tabId).classList.add('active');
    event.target.classList.add('active');
    
    // 如果切换到原文查看标签页，加载数据列表和PDF
    if (tabId === 'source-tab' && currentPaperData) {
        loadSourceDataList();
        // 延迟加载PDF，确保DOM已更新
        setTimeout(() => {
            initPDFViewer();
        }, 100);
    }
}

// 初始化粘贴区域
function initPasteArea() {
    const pasteArea = document.getElementById('paste-area');
    const canvas = document.getElementById('paste-canvas');
    const preview = document.getElementById('paste-preview');
    
    // 监听粘贴事件
    document.addEventListener('paste', (e) => {
        if (!document.getElementById('smiles-tab').classList.contains('active')) {
            return;
        }
        
        const items = e.clipboardData.items;
        
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                const reader = new FileReader();
                
                reader.onload = (event) => {
                    const img = new Image();
                    img.onload = () => {
                        canvas.width = img.width;
                        canvas.height = img.height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0);
                        
                        preview.src = event.target.result;
                        preview.classList.remove('hidden');
                        canvas.classList.add('hidden');
                        pasteArea.querySelector('.paste-placeholder').classList.add('hidden');
                        pasteArea.classList.add('active');
                        
                        currentImageData = event.target.result;
                        document.getElementById('recognize-btn').disabled = false;
                    };
                    img.src = event.target.result;
                };
                
                reader.readAsDataURL(blob);
                e.preventDefault();
                showToast('图片已粘贴', 'success');
                break;
            }
        }
    });
    
    // 拖拽支持
    pasteArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        pasteArea.classList.add('active');
    });
    
    pasteArea.addEventListener('dragleave', () => {
        pasteArea.classList.remove('active');
    });
    
    pasteArea.addEventListener('drop', (e) => {
        e.preventDefault();
        pasteArea.classList.remove('active');
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) {
            loadImageFile(files[0]);
        }
    });
}

// 初始化图片上传
function initImageUpload() {
    const uploadInput = document.getElementById('image-upload');
    uploadInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            loadImageFile(e.target.files[0]);
        }
    });
}

// 加载图片文件
function loadImageFile(file) {
    const reader = new FileReader();
    const preview = document.getElementById('paste-preview');
    const pasteArea = document.getElementById('paste-area');
    
    reader.onload = (event) => {
        preview.src = event.target.result;
        preview.classList.remove('hidden');
        pasteArea.querySelector('.paste-placeholder').classList.add('hidden');
        pasteArea.classList.add('active');
        
        currentImageData = event.target.result;
        document.getElementById('recognize-btn').disabled = false;
    };
    
    reader.readAsDataURL(file);
}

// 识别图片
async function recognizeImage() {
    if (!currentImageData) {
        showToast('请先选择或粘贴图片', 'error');
        return;
    }
    
    const recognizeBtn = document.getElementById('recognize-btn');
    
    // 如果已经在识别中，提示用户等待（串行处理）
    if (recognizeBtn.disabled && recognizeBtn.textContent === '识别中...') {
        showToast('正在识别中，请稍候（串行处理）...', 'info');
        return;
    }
    
    recognizeBtn.disabled = true;
    recognizeBtn.textContent = '识别中...';
    
    try {
        // 将base64转换为blob
        const response = await fetch(currentImageData);
        const blob = await response.blob();
        
        const formData = new FormData();
        formData.append('image', blob, 'image.png');
        
        // 增加超时时间，因为串行处理可能需要更长时间
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000); // 90秒超时
        
        const result = await fetch('/api/recognize', {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        const data = await result.json();
        
        if (data.success) {
            document.getElementById('smiles-result').value = data.smiles;
            document.getElementById('confidence-value').textContent = 
                data.confidence ? (data.confidence * 100).toFixed(1) + '%' : 'N/A';
            document.getElementById('recognition-result').classList.remove('hidden');
            showToast('识别成功', 'success');
        } else {
            showToast('识别失败: ' + data.message, 'error');
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            showToast('识别超时，请重试', 'error');
        } else {
            showToast('识别失败: ' + error.message, 'error');
        }
    } finally {
        recognizeBtn.disabled = false;
        recognizeBtn.textContent = '识别SMILES';
    }
}

// 加载化合物选择器
function loadCompoundSelect() {
    const select = document.getElementById('compound-select');
    
    if (!currentPaperData || !currentPaperData.photophysical_data) {
        select.innerHTML = '<option>暂无数据</option>';
        return;
    }
    
    const compounds = currentPaperData.photophysical_data.map((item, idx) => {
        const id = item.paper_local_id || `化合物${idx + 1}`;
        return `<option value="${idx}">${id}</option>`;
    });
    
    select.innerHTML = compounds.join('');
}

// 填充SMILES
async function fillSmiles() {
    const select = document.getElementById('compound-select');
    const smiles = document.getElementById('smiles-result').value;
    
    if (!smiles) {
        showToast('请先识别SMILES', 'error');
        return;
    }
    
    const idx = parseInt(select.value);
    
    if (currentPaperData && currentPaperData.photophysical_data && currentPaperData.photophysical_data[idx]) {
        currentPaperData.photophysical_data[idx].smiles = smiles;
        
        // 强制更新表格显示（清除缓存）
        currentDataType = 'photophysical';
        loadPaperData();
        
        // 自动保存并同步到数据库
        try {
            const response = await fetch(`/api/papers/${currentPaperId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    photophysical_data: currentPaperData.photophysical_data,
                    device_data: currentPaperData.device_data
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showToast('已填充到数据并同步到数据库', 'success');
                // 重新加载数据以确保同步
                setTimeout(() => {
                    openPaperModal(currentPaperId);
                }, 500);
            } else {
                showToast('填充成功，但同步到数据库失败: ' + result.message, 'warning');
            }
        } catch (error) {
            showToast('填充成功，但同步到数据库失败: ' + error.message, 'warning');
        }
    }
}

// 弹窗缩放相关变量
let modalZoomLevels = {};

// 显示弹窗
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // 重置缩放（如果之前有设置）
    if (modalZoomLevels[modalId]) {
        resetModalZoom(modalId);
    } else {
        modalZoomLevels[modalId] = 1.0;
    }
}

// 关闭弹窗
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    modal.classList.remove('active');
    modal.classList.remove('fullscreen-active');
    const content = modal.querySelector('.modal-content');
    if (content) {
        content.classList.remove('fullscreen');
    }
    document.body.style.overflow = '';
    
    // 重置缩放
    resetModalZoom(modalId);
}

// 弹窗放大
function zoomModalIn(modalId) {
    if (!modalZoomLevels[modalId]) {
        modalZoomLevels[modalId] = 1.0;
    }
    modalZoomLevels[modalId] = Math.min(modalZoomLevels[modalId] + 0.1, 2.0);
    applyModalZoom(modalId);
}

// 弹窗缩小
function zoomModalOut(modalId) {
    if (!modalZoomLevels[modalId]) {
        modalZoomLevels[modalId] = 1.0;
    }
    modalZoomLevels[modalId] = Math.max(modalZoomLevels[modalId] - 0.1, 0.5);
    applyModalZoom(modalId);
}

// 重置弹窗缩放
function resetModalZoom(modalId) {
    modalZoomLevels[modalId] = 1.0;
    applyModalZoom(modalId);
}

// 应用弹窗缩放
function applyModalZoom(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    const content = modal.querySelector('.modal-content');
    if (!content) return;
    
    const zoom = modalZoomLevels[modalId] || 1.0;
    
    // 如果不在全屏模式，应用缩放
    if (!content.classList.contains('fullscreen')) {
        content.style.transform = `scale(${zoom})`;
        content.style.transformOrigin = 'center center';
    } else {
        content.style.transform = '';
    }
    
    // 更新缩放级别显示（查找该弹窗内的zoom-level元素）
    const zoomLevel = content.querySelector('.modal-zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = `${Math.round(zoom * 100)}%`;
    }
}

// 切换全屏
function toggleModalFullscreen(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    const content = modal.querySelector('.modal-content');
    if (!content) return;
    
    // 查找该弹窗内的全屏按钮
    const fullscreenBtn = content.querySelector('.modal-btn[onclick*="toggleModalFullscreen"]');
    
    if (content.classList.contains('fullscreen')) {
        // 退出全屏
        content.classList.remove('fullscreen');
        modal.classList.remove('fullscreen-active');
        if (fullscreenBtn) {
            fullscreenBtn.textContent = '⛶';
            fullscreenBtn.title = '全屏';
        }
        // 恢复之前的缩放
        applyModalZoom(modalId);
    } else {
        // 进入全屏
        content.classList.add('fullscreen');
        modal.classList.add('fullscreen-active');
        if (fullscreenBtn) {
            fullscreenBtn.textContent = '⛶';
            fullscreenBtn.title = '退出全屏';
        }
        // 全屏时重置缩放
        content.style.transform = '';
        modalZoomLevels[modalId] = 1.0;
        const zoomLevel = content.querySelector('.modal-zoom-level');
        if (zoomLevel) {
            zoomLevel.textContent = '100%';
        }
    }
}

// 显示提示消息
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const messageEl = document.getElementById('toast-message');
    
    messageEl.textContent = message;
    toast.className = 'toast ' + type;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// 格式化日期
function formatDate(dateStr) {
    if (!dateStr) return '未知';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN');
}

// 点击弹窗外部关闭
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
});

// 加载抽取配置列表
async function loadExtractionConfigs() {
    const select = document.getElementById('extraction-config');
    if (!select) return;
    
    try {
        const response = await fetch('/api/configs');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const result = await response.json();
        
        if (result.success) {
            // 清空现有选项（保留默认选项）
            select.innerHTML = '<option value="">使用默认配置</option>';
            
            result.configs.forEach(config => {
                const option = document.createElement('option');
                option.value = config.name;
                option.textContent = config.name + (config.description ? ` - ${config.description}` : '');
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 显示配置管理弹窗
function showConfigModal() {
    showModal('config-modal');
    showConfigTab('config-list');
    loadConfigsList();
}

// 配置标签页切换
function showConfigTab(tabId) {
    document.querySelectorAll('.config-tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.config-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.getElementById(tabId).classList.add('active');
    const buttons = document.querySelectorAll('.config-tabs .tab-btn');
    if (tabId === 'config-list') {
        buttons[0].classList.add('active');
    } else {
        buttons[1].classList.add('active');
    }
}

// 加载配置列表
async function loadConfigsList() {
    const container = document.getElementById('configs-list-container');
    if (!container) return;
    
    container.innerHTML = '<p class="loading">加载中...</p>';
    
    try {
        const response = await fetch('/api/configs', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const text = await response.text();
            console.error('API响应错误:', response.status, text);
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 200)}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            if (result.configs && result.configs.length > 0) {
                container.innerHTML = result.configs.map(config => {
                    const safeName = (config.name || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    return `
                    <div class="config-item">
                        <div class="config-info">
                            <h4>${config.name || '未命名'}</h4>
                            <p class="config-desc">${config.description || '无描述'}</p>
                        </div>
                        <div class="config-actions">
                            <button class="btn btn-sm" onclick="editConfig('${safeName}')">编辑</button>
                            <button class="btn btn-sm" onclick="deleteConfigConfirm('${safeName}')">删除</button>
                        </div>
                    </div>
                `;
                }).join('');
            } else {
                container.innerHTML = '<p class="loading">暂无配置，请创建新配置</p>';
            }
        } else {
            container.innerHTML = '<p class="loading">加载失败: ' + (result.message || '未知错误') + '</p>';
        }
    } catch (error) {
        container.innerHTML = '<p class="loading">加载失败: ' + error.message + '</p>';
        console.error('加载配置列表错误:', error);
    }
}

// 编辑配置
async function editConfig(configName) {
    try {
        const response = await fetch(`/api/configs/${encodeURIComponent(configName)}`);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 100)}`);
        }
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('config-name').value = result.config.name || configName;
            document.getElementById('config-description').value = result.config.description || '';
            
            // 加载字段配置到复选框
            loadFieldsToCheckboxes(result.config.fields || {});
            
            showConfigTab('config-editor');
        } else {
            showToast('加载配置失败: ' + result.message, 'error');
        }
    } catch (error) {
        showToast('加载配置失败: ' + error.message, 'error');
        console.error('加载配置错误:', error);
    }
}

// 加载字段到复选框
function loadFieldsToCheckboxes(fields) {
    // 清空所有复选框
    document.querySelectorAll('#photophysical-fields input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    document.querySelectorAll('#device-fields input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    
    // 设置光物性字段
    if (fields.photophysical && fields.photophysical.fields) {
        fields.photophysical.fields.forEach(field => {
            const checkbox = document.getElementById(`pp-${field}`);
            if (checkbox) {
                checkbox.checked = true;
            } else {
                // 添加自定义字段
                addCustomField('photophysical', field);
            }
        });
    }
    
    // 设置器件字段
    if (fields.device && fields.device.fields) {
        fields.device.fields.forEach(field => {
            const checkbox = document.getElementById(`dev-${field}`);
            if (checkbox) {
                checkbox.checked = true;
            } else {
                // 添加自定义字段
                addCustomField('device', field);
            }
        });
    }
}

// 添加自定义字段
function addCustomField(type, fieldName) {
    const container = type === 'photophysical' ? 
        document.getElementById('photophysical-fields') : 
        document.getElementById('device-fields');
    
    const fieldId = `${type === 'photophysical' ? 'pp' : 'dev'}-${fieldName}`;
    
    // 检查是否已存在
    if (document.getElementById(fieldId)) {
        return;
    }
    
    const fieldItem = document.createElement('div');
    fieldItem.className = 'field-item';
    fieldItem.innerHTML = `
        <input type="checkbox" id="${fieldId}" checked>
        <label for="${fieldId}">${fieldName}</label>
    `;
    container.appendChild(fieldItem);
}

// 从复选框获取字段配置
function getFieldsFromCheckboxes() {
    const fields = {
        photophysical: { fields: [] },
        device: { fields: [] }
    };
    
    // 获取光物性字段
    document.querySelectorAll('#photophysical-fields input[type="checkbox"]:checked').forEach(cb => {
        const fieldName = cb.id.replace('pp-', '');
        fields.photophysical.fields.push(fieldName);
    });
    
    // 获取器件字段
    document.querySelectorAll('#device-fields input[type="checkbox"]:checked').forEach(cb => {
        const fieldName = cb.id.replace('dev-', '');
        fields.device.fields.push(fieldName);
    });
    
    return fields;
}

// 保存配置
async function saveConfig() {
    const name = document.getElementById('config-name').value;
    const description = document.getElementById('config-description').value;
    
    if (!name) {
        showToast('请输入配置名称', 'error');
        return;
    }
    
    // 从复选框获取字段配置
    const fields = getFieldsFromCheckboxes();
    
    const configData = {
        name: name,
        description: description,
        fields: fields
    };
    
    try {
        const response = await fetch('/api/configs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        });
        
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 100)}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            showToast('配置保存成功', 'success');
            loadExtractionConfigs();
            loadConfigsList();
            // 清空表单
            document.getElementById('config-name').value = '';
            document.getElementById('config-description').value = '';
            // 重置复选框
            document.querySelectorAll('#photophysical-fields input[type="checkbox"]').forEach(cb => {
                cb.checked = false;
            });
            document.querySelectorAll('#device-fields input[type="checkbox"]').forEach(cb => {
                cb.checked = false;
            });
        } else {
            showToast('保存失败: ' + result.message, 'error');
        }
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
        console.error('保存配置错误:', error);
    }
}

// 删除配置确认
function deleteConfigConfirm(configName) {
    if (confirm(`确定要删除配置 "${configName}" 吗？`)) {
        deleteConfig(configName);
    }
}

// 删除配置
async function deleteConfig(configName) {
    try {
        const response = await fetch(`/api/configs/${encodeURIComponent(configName)}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 100)}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            showToast('配置删除成功', 'success');
            loadExtractionConfigs();
            loadConfigsList();
        } else {
            showToast('删除失败: ' + result.message, 'error');
        }
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
        console.error('删除配置错误:', error);
    }
}

// 加载数据库表列表
async function loadDatabaseTables() {
    const select = document.getElementById('table-select');
    if (!select) return;
    
    select.innerHTML = '<option value="">加载中...</option>';
    
    try {
        const response = await fetch('/api/database/tables');
        if (!response.ok) {
            const text = await response.text();
            console.error('API响应错误:', response.status, text);
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 200)}`);
        }
        const result = await response.json();
        
        if (result.success) {
            select.innerHTML = '<option value="">请选择表</option>';
            if (result.tables && result.tables.length > 0) {
                result.tables.forEach(table => {
                    const option = document.createElement('option');
                    option.value = table.name;
                    option.textContent = `${table.name} (${table.count} 条记录)`;
                    select.appendChild(option);
                });
            } else {
                select.innerHTML = '<option value="">暂无可用表</option>';
            }
        } else {
            select.innerHTML = '<option value="">加载失败: ' + (result.message || '未知错误') + '</option>';
            console.error('加载表列表失败:', result.message);
        }
    } catch (error) {
        console.error('加载数据库表列表失败:', error);
        if (select) {
            select.innerHTML = '<option value="">加载失败: ' + error.message + '</option>';
        }
    }
}

// 刷新表列表
function refreshTables() {
    loadDatabaseTables();
    showToast('已刷新', 'success');
}

// 加载表数据
async function loadTableData(page = 1) {
    const tableSelect = document.getElementById('table-select');
    const container = document.getElementById('table-data-container');
    const searchInput = document.getElementById('table-search');
    
    if (!tableSelect || !container) return;
    
    const tableName = tableSelect.value;
    if (!tableName) {
        container.innerHTML = '<p class="loading">请选择一个表</p>';
        return;
    }
    
    currentTable = tableName;
    currentPage = page;
    currentSearch = searchInput ? searchInput.value.trim() : '';
    
    container.innerHTML = '<p class="loading">加载中...</p>';
    
    try {
        const params = new URLSearchParams({
            page: page.toString(),
            per_page: '50'
        });
        
        if (currentSearch) {
            params.append('search', currentSearch);
        }
        
        const response = await fetch(`/api/database/${tableName}?${params.toString()}`);
        if (!response.ok) {
            const text = await response.text();
            console.error('API响应错误:', response.status, text);
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 200)}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            tablePagination = result.pagination;
            displayTableData(result.data, result.columns);
            updatePaginationControls();
        } else {
            container.innerHTML = '<p class="loading">加载失败: ' + (result.message || '未知错误') + '</p>';
            console.error('加载表数据失败:', result.message);
        }
    } catch (error) {
        container.innerHTML = '<p class="loading">加载失败: ' + error.message + '</p>';
        console.error('加载表数据错误:', error);
        showToast('加载表数据失败: ' + error.message, 'error');
    }
}

// 显示表数据
function displayTableData(data, columns) {
    const container = document.getElementById('table-data-container');
    const paginationInfo = document.getElementById('pagination-info');
    
    if (!container) return;
    
    if (data.length === 0) {
        container.innerHTML = '<p class="loading">暂无数据</p>';
        if (paginationInfo) {
            paginationInfo.textContent = '共 0 条记录';
        }
        return;
    }
    
    // 构建表格
    let html = '<table class="database-table"><thead><tr>';
    columns.forEach(col => {
        html += `<th>${col.name}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    data.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            const value = row[col.name];
            let displayValue = value;
            
            if (value === null || value === undefined) {
                displayValue = '<span style="color: #999;">-</span>';
            } else if (typeof value === 'string' && value.length > 50) {
                displayValue = value.substring(0, 50) + '...';
            } else {
                displayValue = String(value);
            }
            
            html += `<td title="${value || ''}">${displayValue}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
    
    // 更新分页信息
    if (paginationInfo && tablePagination) {
        const { page, per_page, total, pages } = tablePagination;
        const start = (page - 1) * per_page + 1;
        const end = Math.min(page * per_page, total);
        paginationInfo.textContent = `显示 ${start}-${end} / 共 ${total} 条记录 (第 ${page}/${pages} 页)`;
    }
}

// 更新分页控件
function updatePaginationControls() {
    const controls = document.getElementById('pagination-controls');
    if (!controls || !tablePagination) return;
    
    const { page, pages } = tablePagination;
    
    let html = '';
    
    // 上一页按钮
    html += `<button onclick="loadTableData(${page - 1})" ${page <= 1 ? 'disabled' : ''}>上一页</button>`;
    
    // 页码信息
    html += `<span class="page-info">第 ${page} / ${pages} 页</span>`;
    
    // 下一页按钮
    html += `<button onclick="loadTableData(${page + 1})" ${page >= pages ? 'disabled' : ''}>下一页</button>`;
    
    controls.innerHTML = html;
}

// 处理表格搜索
function handleTableSearch(event) {
    if (event.key === 'Enter') {
        loadTableData(1);
    }
}

// 原文查看相关变量
let sourceDataType = 'photophysical';
let currentHighlightedItem = null;

// 切换原文查看数据类型
function switchSourceDataType(type) {
    sourceDataType = type;
    
    // 更新按钮状态
    document.querySelectorAll('.data-type-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    loadSourceDataList();
}

// 加载原文查看的数据表格
function loadSourceDataList() {
    const container = document.getElementById('source-data-table-container');
    if (!container || !currentPaperData) return;
    
    const data = currentPaperData[sourceDataType + '_data'] || [];
    
    if (data.length === 0) {
        container.innerHTML = '<p class="loading">暂无数据</p>';
        return;
    }
    
    // 获取所有字段名（排除table_id等元数据字段）
    const excludeFields = ['table_id', 'source_snippet', 'note', 'quality_flag'];
    const allFields = new Set();
    data.forEach(item => {
        Object.keys(item).forEach(key => {
            if (!excludeFields.includes(key)) {
                allFields.add(key);
            }
        });
    });
    
    const fields = Array.from(allFields);
    
    // 构建表格
    let html = '<table class="source-data-table"><thead><tr>';
    fields.forEach(field => {
        html += `<th>${field}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    data.forEach((item, idx) => {
        html += `<tr onclick="viewSourceData(${idx})" data-index="${idx}">`;
        fields.forEach(field => {
            const value = item[field];
            let displayValue = value;
            
            if (value === null || value === undefined) {
                displayValue = '<span style="color: #999;">-</span>';
            } else if (typeof value === 'number') {
                displayValue = value;
            } else {
                displayValue = String(value);
            }
            
            html += `<td>${displayValue}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

// PDF查看器相关变量
let currentZoom = 1.0;
let pdfViewerMode = 'iframe'; // 'iframe' 或 'canvas'

// 查看原文数据（显示PDF）
async function viewSourceData(index) {
    if (!currentPaperData) return;
    
    const data = currentPaperData[sourceDataType + '_data'] || [];
    if (index >= data.length) return;
    
    const item = data[index];
    
    // 更新选中状态
    const container = document.getElementById('source-data-table-container');
    if (container) {
        container.querySelectorAll('tbody tr').forEach(tr => {
            tr.classList.remove('active');
        });
        const selectedRow = container.querySelector(`tbody tr[data-index="${index}"]`);
        if (selectedRow) {
            selectedRow.classList.add('active');
        }
    }
    
    currentHighlightedItem = item;
    
    // 加载PDF（直接加载，不定位）
    try {
        const response = await fetch(`/api/papers/${currentPaperId}/source`);
        
        // 检查响应状态
        if (!response.ok) {
            const text = await response.text();
            console.error('API响应错误:', response.status, text);
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 200)}`);
        }
        
        // 检查Content-Type
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('响应不是JSON格式:', contentType, text.substring(0, 200));
            throw new Error('服务器返回的不是JSON格式数据');
        }
        
        const result = await response.json();
        
        if (result.success && result.pdf_url) {
            displayPDF(result.pdf_url);
        } else {
            document.getElementById('source-content').innerHTML = '<p class="loading">加载失败: ' + (result.message || '未知错误') + '</p>';
        }
    } catch (error) {
        console.error('加载PDF错误:', error);
        document.getElementById('source-content').innerHTML = '<p class="loading">加载失败: ' + error.message + '</p>';
    }
}

// 显示PDF
function displayPDF(pdfUrl) {
    const container = document.getElementById('source-content');
    if (!container) return;
    
    // 重置缩放
    currentZoom = 1.0;
    
    // 使用iframe显示PDF，添加#toolbar=0隐藏浏览器默认工具栏
    container.innerHTML = `<iframe src="${pdfUrl}#toolbar=0" type="application/pdf" style="width: 100%; height: 600px; min-height: 600px; border: none;"></iframe>`;
    
    // 更新缩放级别显示
    updateZoomDisplay();
}

// 放大
function zoomIn() {
    currentZoom = Math.min(currentZoom + 0.25, 3.0);
    applyZoom();
}

// 缩小
function zoomOut() {
    currentZoom = Math.max(currentZoom - 0.25, 0.5);
    applyZoom();
}

// 重置缩放
function resetZoom() {
    currentZoom = 1.0;
    applyZoom();
}

// 适应宽度
function fitWidth() {
    const container = document.getElementById('source-content');
    if (!container) return;
    
    const iframe = container.querySelector('iframe');
    if (iframe) {
        iframe.style.width = '100%';
        iframe.style.height = 'auto';
        iframe.style.minHeight = '600px';
    }
    currentZoom = 1.0;
    updateZoomDisplay();
}

// 适应页面
function fitPage() {
    const container = document.getElementById('source-content');
    if (!container) return;
    
    const iframe = container.querySelector('iframe');
    if (iframe) {
        iframe.style.width = '100%';
        iframe.style.height = '100vh';
    }
    currentZoom = 1.0;
    updateZoomDisplay();
}

// 应用缩放
function applyZoom() {
    const container = document.getElementById('source-content');
    if (!container) return;
    
    const iframe = container.querySelector('iframe');
    if (iframe) {
        // 对于iframe，使用transform来缩放，保持原始尺寸
        iframe.style.transform = `scale(${currentZoom})`;
        iframe.style.transformOrigin = 'top left';
        
        // 调整容器尺寸以适应缩放后的内容
        const viewerContainer = document.getElementById('pdf-viewer-container');
        if (viewerContainer) {
            const baseHeight = 600;
            viewerContainer.style.height = `${baseHeight * currentZoom}px`;
        }
    }
    
    updateZoomDisplay();
}

// 更新缩放级别显示
function updateZoomDisplay() {
    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
    }
}

// 显示原文内容并高亮
function displaySourceContent(paragraphs, tables, dataItem) {
    const container = document.getElementById('source-content');
    if (!container) return;
    
    // 检查数据是否为空
    if ((!paragraphs || paragraphs.length === 0) && (!tables || tables.length === 0)) {
        container.innerHTML = '<p class="loading">该论文暂无原文数据，可能需要重新处理PDF</p>';
        return;
    }
    
    let html = '';
    
    // 提取要搜索的关键词
    const searchTerms = [];
    if (dataItem.paper_local_id) searchTerms.push(String(dataItem.paper_local_id));
    if (dataItem.name) searchTerms.push(String(dataItem.name));
    if (dataItem.smiles) searchTerms.push(String(dataItem.smiles));
    if (dataItem.emitter_name) searchTerms.push(String(dataItem.emitter_name));
    
    // 添加数值关键词（只添加有意义的数值）
    Object.entries(dataItem).forEach(([k, v]) => {
        if (v !== null && v !== '' && typeof v === 'number' && !isNaN(v) && v !== 0) {
            // 避免添加过小的数值（可能是ID）
            if (v > 1 || v < -1) {
                searchTerms.push(String(v));
            }
        }
    });
    
    // 显示段落
    if (paragraphs && paragraphs.length > 0) {
        paragraphs.forEach(para => {
            if (!para || !para.text) return;
            
            let text = String(para.text);
            // 先转义HTML，避免XSS攻击
            text = escapeHtml(text);
            let highlighted = false;
            
            // 高亮关键词（在转义后进行）
            searchTerms.forEach(term => {
                if (term && term.trim()) {
                    // 转义搜索词中的特殊字符
                    const escapedTerm = escapeHtml(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regex = new RegExp(`(${escapedTerm})`, 'gi');
                    if (text.includes(escapedTerm)) {
                        text = text.replace(regex, '<span class="highlight">$1</span>');
                        highlighted = true;
                    }
                }
            });
            
            const highlightClass = highlighted ? 'highlighted' : '';
            const sectionInfo = para.section ? `<span class="section-tag">${escapeHtml(para.section)}</span>` : '';
            html += `<div class="paragraph ${highlightClass}">${sectionInfo}${text}</div>`;
        });
    }
    
    // 显示表格
    if (tables && tables.length > 0) {
        tables.forEach(table => {
            if (!table) return;
            
            // 检查是否包含相关数据
            const tableText = (table.caption || '') + ' ' + (table.markdown_table || '');
            let tableHighlighted = false;
            
            searchTerms.forEach(term => {
                if (term && term.trim() && tableText.includes(term)) {
                    tableHighlighted = true;
                }
            });
            
            const highlightClass = tableHighlighted ? 'highlighted' : '';
            html += `
                <div class="table-section ${highlightClass}">
                    <div class="table-caption">${escapeHtml(table.caption || '表格')}</div>
                    <div class="table-content">${escapeHtml(table.markdown_table || '')}</div>
                </div>
            `;
        });
    }
    
    container.innerHTML = html || '<p class="loading">暂无原文内容</p>';
    
    // 滚动到第一个高亮
    if (searchTerms.length > 0) {
        setTimeout(() => {
            const firstHighlight = container.querySelector('.highlighted, .highlight');
            if (firstHighlight) {
                firstHighlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }, 100);
    }
}

// 转义HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 初始化PDF查看器（当切换到原文查看标签页时）
function initPDFViewer() {
    if (!currentPaperData) return;
    
    // 自动加载PDF（如果有数据）
    const data = currentPaperData[sourceDataType + '_data'] || [];
    if (data.length > 0) {
        // 自动选择第一个数据项并加载PDF
        viewSourceData(0);
    } else {
        // 如果没有数据，直接加载PDF
        loadPDFDirectly();
    }
}

// 直接加载PDF（不选择数据项）
async function loadPDFDirectly() {
    if (!currentPaperId) return;
    
    try {
        const response = await fetch(`/api/papers/${currentPaperId}/source`);
        const result = await response.json();
        
        if (result.success && result.pdf_url) {
            displayPDF(result.pdf_url);
        } else {
            document.getElementById('source-content').innerHTML = '<p class="loading">加载失败: ' + (result.message || '未知错误') + '</p>';
        }
    } catch (error) {
        console.error('加载PDF错误:', error);
        document.getElementById('source-content').innerHTML = '<p class="loading">加载失败: ' + error.message + '</p>';
    }
}

// 初始化自定义字段输入
function initConfigCustomFields() {
    const ppInput = document.getElementById('pp-custom-field');
    const devInput = document.getElementById('dev-custom-field');
    
    if (ppInput) {
        ppInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && ppInput.value.trim()) {
                addCustomField('photophysical', ppInput.value.trim());
                ppInput.value = '';
            }
        });
    }
    
    if (devInput) {
        devInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && devInput.value.trim()) {
                addCustomField('device', devInput.value.trim());
                devInput.value = '';
            }
        });
    }
}

