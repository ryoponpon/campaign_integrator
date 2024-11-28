document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const processButton = document.getElementById('process-button');
    const progress = document.getElementById('progress');
    
    let files = [];

    // ドラッグ&ドロップイベントの処理
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    function handleFiles(fileList) {
        const formData = new FormData();
        
        for (const file of fileList) {
            if (file.name.toLowerCase().endsWith('.csv')) {
                formData.append('files[]', file);
            }
        }

        // アップロード中の表示
        const uploadingDiv = document.createElement('div');
        uploadingDiv.className = 'uploading';
        uploadingDiv.textContent = 'アップロード中...';
        fileList.appendChild(uploadingDiv);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            fileList.removeChild(uploadingDiv);
            if (data.success) {
                files = files.concat(data.files);
                updateFileList();
                processButton.style.display = 'block';
            } else {
                showError('アップロードに失敗しました: ' + data.error);
            }
        })
        .catch(error => {
            fileList.removeChild(uploadingDiv);
            console.error('Error:', error);
            showError('アップロードに失敗しました');
        });
    }

    function updateFileList() {
        fileList.innerHTML = '';
        files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            
            const fileName = document.createElement('span');
            fileName.textContent = file;
            
            const removeButton = document.createElement('button');
            removeButton.className = 'remove-button';
            removeButton.textContent = '削除';
            removeButton.onclick = () => removeFile(file);
            
            fileItem.appendChild(fileName);
            fileItem.appendChild(removeButton);
            fileList.appendChild(fileItem);
        });
    }

    function removeFile(filename) {
        files = files.filter(f => f !== filename);
        updateFileList();
        if (files.length === 0) {
            processButton.style.display = 'none';
        }
    }

    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        document.querySelector('.container').appendChild(errorDiv);
        setTimeout(() => {
            errorDiv.remove();
        }, 3000);
    }

    processButton.addEventListener('click', () => {
        if (files.length === 0) {
            showError('ファイルを選択してください');
            return;
        }

        processButton.style.display = 'none';
        progress.style.display = 'block';

        fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ files: files })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.redirect) {
                window.location.href = data.redirect;
            } else {
                showError('処理に失敗しました');
                processButton.style.display = 'block';
                progress.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('処理に失敗しました');
            processButton.style.display = 'block';
            progress.style.display = 'none';
        });
    });

    // エラーメッセージのスタイリング用のCSSを動的に追加
    const style = document.createElement('style');
    style.textContent = `
        .error-message {
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: var(--danger-color);
            color: white;
            padding: 1rem;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            animation: slideIn 0.3s ease-out, fadeOut 0.3s ease-in 2.7s;
            z-index: 1000;
        }

        .uploading {
            text-align: center;
            padding: 1rem;
            color: var(--primary-color);
            font-weight: 500;
        }

        .remove-button {
            padding: 0.4rem 0.8rem;
            background-color: var(--danger-color);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .remove-button:hover {
            background-color: #c82333;
            transform: translateY(-1px);
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes fadeOut {
            from {
                opacity: 1;
            }
            to {
                opacity: 0;
            }
        }

        .file-item {
            animation: fadeIn 0.3s ease-out;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);
});