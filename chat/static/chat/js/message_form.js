function initChatSocket(options) {
    const {
        conversationId,
        currentUserId,
        chatContainerId = 'chatMessages',
        homeworkUrlTemplate = null,
        fileUrlTemplate = null,
        formId,
        textareaId,
        fileInputId = null,
        fileChipId = null,
    } = options;

    if (!conversationId) return;

    const chatContainer = document.getElementById(chatContainerId);
    const form = document.getElementById(formId);
    const textarea = document.getElementById(textareaId);
    if (!chatContainer || !form || !textarea) return;

    const escapeHtml = (str) => {
        const div = document.createElement('div');
        div.textContent = str == null ? '' : str;
        return div.innerHTML;
    };

    const buildBubble = (data) => {
        const isOwn = String(data.sender_id) === String(currentUserId);
        let html = `<div class="chat-bubble ${isOwn ? 'own' : 'other'}">`;
        html += `<div class="chat-sender">${escapeHtml(data.sender_name)}</div>`;
        if (data.text) html += escapeHtml(data.text);

        const hasText = Boolean(data.text);

        if (data.has_file && fileUrlTemplate) {
            const url = fileUrlTemplate.replace('0', data.message_id);
            if (hasText) html += '<br>';
            html += `<a href="${url}" class="chat-file-link" target="_blank" rel="noopener">` +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>' +
                '</svg>Прикріплений файл</a>';
        }

        if (data.homework_id && homeworkUrlTemplate) {
            const url = homeworkUrlTemplate.replace('0', data.homework_id);
            if (hasText || data.has_file) html += '<br>';
            html += `<a href="${url}" class="chat-homework-link">` +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>' +
                '<polyline points="14 2 14 8 20 8"></polyline></svg>' +
                `<span>${escapeHtml(data.homework_title)}</span></a>`;
        }

        html += '</div>';
        return html;
    };

    const fileInput = fileInputId ? document.getElementById(fileInputId) : null;
    const fileChip = fileChipId ? document.getElementById(fileChipId) : null;

    const clearAttachedFile = () => {
        if (fileInput) fileInput.value = '';
        if (fileChip) fileChip.innerHTML = '';
    };

    let socket = null;
    let reconnectDelay = 1000;
    let reconnectTimer = null;
    let pageUnloading = false;
    let connectionBanner = null;
    let heartbeatInterval = null;
    let pongTimeout = null;

    const showConnectionBanner = (text) => {
        if (!connectionBanner) {
            connectionBanner = document.createElement('div');
            connectionBanner.className = 'chat-connection-banner';
            form.parentNode.insertBefore(connectionBanner, form);
        }
        connectionBanner.textContent = text;
        connectionBanner.style.display = 'block';
    };

    const hideConnectionBanner = () => {
        if (connectionBanner) connectionBanner.style.display = 'none';
    };

    const stopHeartbeat = () => {
        if (heartbeatInterval) clearInterval(heartbeatInterval);
        if (pongTimeout) clearTimeout(pongTimeout);
        heartbeatInterval = null;
        pongTimeout = null;
    };

    const startHeartbeat = () => {
        stopHeartbeat();
        heartbeatInterval = setInterval(() => {
            if (!socket || socket.readyState !== WebSocket.OPEN) return;

            socket.send(JSON.stringify({ type: 'ping' }));

            pongTimeout = setTimeout(() => {
                if (socket) socket.close();
            }, 10000);
        }, 15000);
    };

    const connectSocket = () => {
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        socket = new WebSocket(`${protocol}${window.location.host}/ws/chat/${conversationId}/`);

        socket.addEventListener('open', () => {
            reconnectDelay = 1000;
            hideConnectionBanner();
            startHeartbeat();
        });

        socket.addEventListener('message', (event) => {
            const data = JSON.parse(event.data);

            if (data.kind === 'pong') {
                if (pongTimeout) clearTimeout(pongTimeout);
                return;
            }

            if (data.kind === 'error') {
                alert(data.message);
                return;
            }

            const emptyState = chatContainer.querySelector('.chat-empty');
            if (emptyState) emptyState.remove();
            chatContainer.insertAdjacentHTML('afterbegin', buildBubble(data));
        });

        socket.addEventListener('close', () => {
            stopHeartbeat();

            if (pageUnloading) return;

            showConnectionBanner('Втрачено з\'єднання, підключення...');

            reconnectTimer = setTimeout(() => {
                connectSocket();
            }, reconnectDelay);

            reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        });
    };

    connectSocket();

    window.addEventListener('beforeunload', () => {
        pageUnloading = true;
        if (reconnectTimer) clearTimeout(reconnectTimer);
        stopHeartbeat();
    });

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState !== 'visible') return;

        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
            pongTimeout = setTimeout(() => {
                if (socket) socket.close();
            }, 10000);
            return;
        }

        if (!socket || socket.readyState === WebSocket.CLOSED) {
            if (reconnectTimer) clearTimeout(reconnectTimer);
            reconnectDelay = 1000;
            connectSocket();
        }
    });

    const uploadFileToR2 = async (file) => {
        const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;

        const urlResponse = await fetch(`/chat/upload-url/${conversationId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ filenames: [file.name] }),
        });

        if (!urlResponse.ok) throw new Error('upload-url request failed');
        const { uploads } = await urlResponse.json();
        const { upload_url, content_type, key } = uploads[0];

        const putResponse = await fetch(upload_url, {
            method: 'PUT',
            headers: { 'Content-Type': content_type },
            body: file,
        });
        if (!putResponse.ok) throw new Error('upload failed');

        return key;
    };

    const sendMessage = async () => {
        const text = textarea.value.trim();
        const hasFile = fileInput && fileInput.files.length > 0;

        if (!text && !hasFile) return;
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            alert('Немає з\'єднання з чатом. Зачекайте на перепідключення.');
            return;
        }

        const homeworkInput = form.querySelector('input[name="homework_id"]');
        const homeworkId = homeworkInput ? homeworkInput.value : null;

        const submitBtn = form.querySelector('button[type="submit"]');
        const originalLabel = submitBtn ? submitBtn.textContent : '';

        let fileKey = '';

        if (hasFile) {
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Завантаження...';
            }
            try {
                fileKey = await uploadFileToR2(fileInput.files[0]);
            } catch (err) {
                alert('Не вдалося завантажити файл. Спробуйте ще раз.');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalLabel;
                }
                return;
            }
        }

        if (!socket || socket.readyState !== WebSocket.OPEN) {
            alert('З\'єднання розірвалося під час завантаження файлу. Спробуйте ще раз.');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = originalLabel;
            }
            return;
        }

        socket.send(JSON.stringify({ text, homework_id: homeworkId, file_key: fileKey }));

        textarea.value = '';
        textarea.dispatchEvent(new Event('input'));
        clearAttachedFile();

        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = originalLabel;
        }
    };

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        sendMessage();
    });
}