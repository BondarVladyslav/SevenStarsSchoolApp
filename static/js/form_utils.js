function autoGrowTextarea(textareaId, maxHeight = 200, overflowClass = 'custom-scroll') {
    const textarea = document.getElementById(textareaId);
    if (!textarea) return;

    const grow = () => {
        textarea.style.height = 'auto';
        const newHeight = Math.min(textarea.scrollHeight, maxHeight);
        textarea.style.height = newHeight + 'px';

        const isOverflowing = textarea.scrollHeight > maxHeight;
        textarea.style.overflowY = isOverflowing ? 'auto' : 'hidden';
        textarea.classList.toggle(overflowClass, isOverflowing);
    };

    textarea.addEventListener('input', grow);
    grow();
}

function initFileChip(fileInputId, chipId, maxFileSize = 15 * 1024 * 1024) {
    const fileInput = document.getElementById(fileInputId);
    const chip = document.getElementById(chipId);
    if (!fileInput || !chip) return;

    let previewUrl = null;

    const render = () => {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = null;
        }

        chip.innerHTML = '';
        if (!fileInput.files.length) return;

        const file = fileInput.files[0];
        previewUrl = URL.createObjectURL(file);

        const name = document.createElement('a');
        name.className = 'file-name-chip-text';
        name.textContent = file.name;
        name.href = previewUrl;
        name.target = '_blank';
        name.rel = 'noopener';
        name.title = 'Відкрити файл';

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'file-chip-remove';
        removeBtn.setAttribute('aria-label', 'Прибрати файл');
        removeBtn.textContent = '\u00d7';
        removeBtn.addEventListener('click', () => {
            fileInput.value = '';
            render();
        });

        chip.appendChild(name);
        chip.appendChild(removeBtn);
    };

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file && file.size > maxFileSize) {
            alert(`Файл "${file.name}" занадто великий (максимум ${Math.round(maxFileSize / 1024 / 1024)} МБ).`);
            fileInput.value = '';
        }
        render();
    });
}

function initFileList(fileInputId, listId, maxFiles = 7, submitButtonId = null, hintId = null, maxFileSize = 15 * 1024 * 1024) {
    const fileInput = document.getElementById(fileInputId);
    const list = document.getElementById(listId);
    if (!fileInput || !list) return;

    const submitBtn = submitButtonId ? document.getElementById(submitButtonId) : null;
    const hint = hintId ? document.getElementById(hintId) : null;
    const baseHintText = hint ? hint.textContent : '';

    let files = [];
    const previewUrls = new Map();

    const getPreviewUrl = (file) => {
        if (!previewUrls.has(file)) {
            previewUrls.set(file, URL.createObjectURL(file));
        }
        return previewUrls.get(file);
    };

    const revokeUnusedPreviews = () => {
        previewUrls.forEach((url, file) => {
            if (!files.includes(file)) {
                URL.revokeObjectURL(url);
                previewUrls.delete(file);
            }
        });
    };

    const syncInput = () => {
        const dt = new DataTransfer();
        files.forEach((file) => dt.items.add(file));
        fileInput.files = dt.files;
    };

    const render = () => {
        revokeUnusedPreviews();
        list.innerHTML = '';

        files.forEach((file, index) => {
            const chip = document.createElement('div');
            chip.className = 'file-chip';

            const name = document.createElement('a');
            name.className = 'file-chip-name';
            name.textContent = file.name;
            name.href = getPreviewUrl(file);
            name.target = '_blank';
            name.rel = 'noopener';
            name.title = 'Відкрити файл';

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'file-chip-remove';
            removeBtn.setAttribute('aria-label', `Видалити файл ${file.name}`);
            removeBtn.textContent = '\u00d7';
            removeBtn.addEventListener('click', () => {
                files.splice(index, 1);
                syncInput();
                render();
            });

            chip.appendChild(name);
            chip.appendChild(removeBtn);
            list.appendChild(chip);
        });

        const isOverLimit = files.length > maxFiles;

        if (submitBtn) submitBtn.disabled = isOverLimit;

        if (hint) {
            hint.classList.toggle('form-hint-error', isOverLimit);
            hint.textContent = isOverLimit
                ? `Забагато файлів: ${files.length} з ${maxFiles} максимум. Приберіть зайві, щоб відправити.`
                : baseHintText;
        }
    };

    fileInput.addEventListener('change', () => {
        const rejected = [];

        Array.from(fileInput.files).forEach((newFile) => {
            if (newFile.size > maxFileSize) {
                rejected.push(newFile.name);
                return;
            }

            const alreadyAdded = files.some(
                (f) => f.name === newFile.name && f.size === newFile.size && f.lastModified === newFile.lastModified
            );
            if (!alreadyAdded) files.push(newFile);
        });

        if (rejected.length > 0) {
            const maxMb = Math.round(maxFileSize / 1024 / 1024);
            alert(`Занадто великі файли (максимум ${maxMb} МБ): ${rejected.join(', ')}`);
        }

        syncInput();
        render();
    });
}

function scrollToBottom(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.scrollTop = el.scrollHeight;
}

function pinScrollToBottom(elementId, attempts = 6) {
    let count = 0;
    const tick = () => {
        scrollToBottom(elementId);
        count += 1;
        if (count < attempts) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    window.addEventListener('load', () => scrollToBottom(elementId));
}