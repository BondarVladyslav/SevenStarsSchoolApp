function initSearchableSelect(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const input = container.querySelector('.searchable-select-input');
    const hiddenInput = container.querySelector('.searchable-select-value');
    const dropdown = container.querySelector('.searchable-select-dropdown');
    const optionEls = Array.from(container.querySelectorAll('.searchable-select-option'));
    const emptyMessage = options.emptyMessage || 'Нічого не знайдено';

    if (!input || !hiddenInput || !dropdown) return;

    let activeIndex = -1;

    const showDropdown = () => dropdown.classList.add('open');
    const hideDropdown = () => {
        dropdown.classList.remove('open');
        activeIndex = -1;
    };

    const visibleOptions = () => optionEls.filter((opt) => opt.style.display !== 'none');

    const updateActiveHighlight = () => {
        optionEls.forEach((opt) => opt.classList.remove('active'));
        const current = visibleOptions()[activeIndex];
        if (current) {
            current.classList.add('active');
            current.scrollIntoView({ block: 'nearest' });
        }
    };

    const filterOptions = () => {
        const query = input.value.trim().toLowerCase();
        let visibleCount = 0;

        optionEls.forEach((opt) => {
            const matchesQuery = opt.textContent.toLowerCase().includes(query);
            const matchesExternal = options.optionFilter ? options.optionFilter(opt) : true;
            const matches = matchesQuery && matchesExternal;
            opt.style.display = matches ? '' : 'none';
            if (matches) visibleCount += 1;
        });

        let emptyEl = dropdown.querySelector('.searchable-select-empty');
        if (visibleCount === 0) {
            if (!emptyEl) {
                emptyEl = document.createElement('div');
                emptyEl.className = 'searchable-select-empty';
                emptyEl.textContent = emptyMessage;
                dropdown.appendChild(emptyEl);
            }
        } else if (emptyEl) {
            emptyEl.remove();
        }

        activeIndex = -1;
        updateActiveHighlight();
    };

    const selectOption = (opt) => {
        hiddenInput.value = opt.dataset.value;
        input.value = opt.textContent.trim();
        hideDropdown();
        if (typeof options.onSelect === 'function') {
            options.onSelect(opt);
        }
    };

    input.addEventListener('input', () => {
        hiddenInput.value = '';
        filterOptions();
        showDropdown();
    });

    input.addEventListener('focus', () => {
        filterOptions();
        showDropdown();
    });

    input.addEventListener('keydown', (event) => {
        const opts = visibleOptions();

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            activeIndex = Math.min(activeIndex + 1, opts.length - 1);
            updateActiveHighlight();
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            updateActiveHighlight();
        } else if (event.key === 'Enter') {
            event.preventDefault();
            if (opts[activeIndex]) selectOption(opts[activeIndex]);
        } else if (event.key === 'Escape') {
            hideDropdown();
        }
    });

    optionEls.forEach((opt) => {
        opt.addEventListener('click', () => selectOption(opt));
    });

    document.addEventListener('click', (event) => {
        if (!container.contains(event.target)) hideDropdown();
    });
    if (options.requireSelection) {
        const form = container.closest('form');
        if (form) {
            form.addEventListener('submit', (event) => {
                if (!hiddenInput.value) {
                    event.preventDefault();
                    input.style.borderColor = '#E24B4A';
                    input.focus();
                    setTimeout(() => { input.style.borderColor = ''; }, 1500);
                }
            });
        }
    }

    return {
        refresh: filterOptions,
        clear: () => {
            hiddenInput.value = '';
            input.value = '';
        },
    };
}

function initListFilter(inputId, itemsSelector, options = {}) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const items = typeof itemsSelector === 'string'
        ? Array.from(document.querySelectorAll(itemsSelector))
        : itemsSelector;

    const emptyMessage = options.emptyMessage || 'Нічого не знайдено';
    const emptyContainer = options.emptyContainer
        ? document.querySelector(options.emptyContainer)
        : input.closest('.content-card');

    let emptyEl = null;

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        let visibleCount = 0;

        items.forEach((item) => {
            const matches = item.textContent.toLowerCase().includes(query);
            item.style.display = matches ? '' : 'none';
            if (matches) visibleCount += 1;
        });

        if (visibleCount === 0 && emptyContainer) {
            if (!emptyEl) {
                emptyEl = document.createElement('div');
                emptyEl.className = 'list-card-empty';
                emptyEl.textContent = emptyMessage;
                emptyContainer.appendChild(emptyEl);
            }
        } else if (emptyEl) {
            emptyEl.remove();
            emptyEl = null;
        }
    });
}

function initEntityListFilter(config) {
    const {
        searchInputId,
        checkboxId,
        itemsSelector,
        emptyContainer,
        emptyMessage = 'Нічого не знайдено',
    } = config;

    const searchInput = searchInputId ? document.getElementById(searchInputId) : null;
    const checkbox = checkboxId ? document.getElementById(checkboxId) : null;
    const items = Array.from(document.querySelectorAll(itemsSelector));
    const emptyContainerEl = emptyContainer ? document.querySelector(emptyContainer) : null;

    if (items.length === 0) return;

    let emptyEl = null;

    const applyFilters = () => {
        const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const onlyWithoutGroup = checkbox ? checkbox.checked : false;
        let visibleCount = 0;

        items.forEach((item) => {
            const matchesSearch = !query || item.textContent.toLowerCase().includes(query);
            const hasGroup = item.dataset.hasGroup === 'true';
            const matchesGroupFilter = !onlyWithoutGroup || !hasGroup;
            const visible = matchesSearch && matchesGroupFilter;

            item.style.display = visible ? '' : 'none';
            if (visible) visibleCount += 1;
        });

        if (visibleCount === 0 && emptyContainerEl) {
            if (!emptyEl) {
                emptyEl = document.createElement('div');
                emptyEl.className = 'list-card-empty';
                emptyEl.textContent = emptyMessage;
                emptyContainerEl.appendChild(emptyEl);
            }
        } else if (emptyEl) {
            emptyEl.remove();
            emptyEl = null;
        }
    };

    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (checkbox) checkbox.addEventListener('change', applyFilters);
}


function initSectionedListFilter(inputId, options) {
    const {
        sectionSelector,
        itemSelector,
        emptyMessage = 'Нічого не знайдено',
        emptyContainer,
    } = options;

    const input = document.getElementById(inputId);
    if (!input) return;

    const sections = Array.from(document.querySelectorAll(sectionSelector));
    const emptyContainerEl = emptyContainer ? document.querySelector(emptyContainer) : input.closest('.detail-main');

    let emptyEl = null;

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        let anyVisible = false;

        sections.forEach((section) => {
            const items = Array.from(section.querySelectorAll(itemSelector));
            let sectionHasVisible = false;

            items.forEach((item) => {
                const matches = !query || item.textContent.toLowerCase().includes(query);
                item.style.display = matches ? '' : 'none';
                if (matches) sectionHasVisible = true;
            });

            section.style.display = sectionHasVisible ? '' : 'none';
            if (sectionHasVisible) anyVisible = true;
        });

        if (!anyVisible && emptyContainerEl) {
            if (!emptyEl) {
                emptyEl = document.createElement('div');
                emptyEl.className = 'list-card-empty';
                emptyEl.textContent = emptyMessage;
                emptyContainerEl.appendChild(emptyEl);
            }
        } else if (emptyEl) {
            emptyEl.remove();
            emptyEl = null;
        }
    });
}