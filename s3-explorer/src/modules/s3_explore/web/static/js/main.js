// File Explorer Application
class FileExplorer {
    constructor() {
        this.currentPath = '';
        this.selectedItems = new Set();
        this.viewMode = 'grid'; // 'grid' or 'list'
        this.folderStructure = {};
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        this.basePath = (window.APP_BASE_PATH || '').replace(/\/$/, '');

        this.initializeElements();
        this.attachEventListeners();
        this.loadFolderStructure();
        this.navigateToFolder('');
    }

    buildUrl(path) {
        // Ensure path starts with /
        if (!path.startsWith('/')) {
            path = '/' + path;
        }
        return this.basePath + path;
    }

    initializeElements() {
        // Main elements
        this.fileList = document.getElementById('fileList');
        this.folderTree = document.getElementById('folderTree');
        this.breadcrumb = document.getElementById('breadcrumb');
        this.contextMenu = document.getElementById('contextMenu');
        this.dropZone = document.getElementById('dropZone');
        this.fileInput = document.getElementById('fileInput');
        this.uploadProgress = document.getElementById('uploadProgress');
        this.emptyState = document.getElementById('emptyState');

        // Buttons
        this.uploadBtn = document.getElementById('uploadBtn');
        this.newFolderBtn = document.getElementById('newFolderBtn');
        this.deleteBtn = document.getElementById('deleteBtn');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.shareBtn = document.getElementById('shareBtn');
        this.selectAllBtn = document.getElementById('selectAllBtn');
        this.gridViewBtn = document.getElementById('gridViewBtn');
        this.listViewBtn = document.getElementById('listViewBtn');

        // Modal
        this.previewModal = document.getElementById('previewModal');
        this.previewContent = document.getElementById('previewContent');
        this.previewTitle = document.getElementById('previewTitle');
        this.closePreview = document.getElementById('closePreview');
    }

    attachEventListeners() {
        // Upload handlers
        this.uploadBtn?.addEventListener('click', () => this.fileInput.click());
        this.fileInput?.addEventListener('change', (e) => this.handleFileSelect(e.target.files));

        // Drag and drop
        this.dropZone?.addEventListener('click', () => this.fileInput.click());
        this.dropZone?.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.dropZone?.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.dropZone?.addEventListener('drop', (e) => this.handleDrop(e));

        // Also add drag-and-drop to the file explorer area
        const fileExplorer = document.getElementById('fileExplorer');
        if (fileExplorer) {
            fileExplorer.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                fileExplorer.classList.add('bg-blue-50');
            });
            fileExplorer.addEventListener('dragleave', (e) => {
                if (e.target === fileExplorer) {
                    fileExplorer.classList.remove('bg-blue-50');
                }
            });
            fileExplorer.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                fileExplorer.classList.remove('bg-blue-50');
                const files = Array.from(e.dataTransfer.files);
                if (files.length > 0) {
                    this.uploadFiles(files);
                }
            });
        }

        // Folder management
        this.newFolderBtn?.addEventListener('click', () => this.createNewFolder());

        // Selection and actions
        this.selectAllBtn?.addEventListener('click', () => this.toggleSelectAll());
        this.deleteBtn?.addEventListener('click', () => this.deleteSelected());
        this.downloadBtn?.addEventListener('click', () => this.downloadSelected());
        this.shareBtn?.addEventListener('click', () => this.shareSelected());

        // View toggle
        this.gridViewBtn?.addEventListener('click', () => this.setViewMode('grid'));
        this.listViewBtn?.addEventListener('click', () => this.setViewMode('list'));

        // Context menu
        document.addEventListener('click', () => this.hideContextMenu());
        this.contextMenu?.addEventListener('click', (e) => this.handleContextMenuAction(e));

        // Preview modal
        this.closePreview?.addEventListener('click', () => this.closePreviewModal());
        this.previewModal?.addEventListener('click', (e) => {
            if (e.target === this.previewModal) this.closePreviewModal();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));

        // Click outside to deselect
        this.fileList?.addEventListener('click', (e) => {
            if (e.target === this.fileList) {
                this.clearSelection();
            }
        });

        // Root folder click handler
        const rootFolder = this.folderTree?.querySelector('.folder-tree-item[data-path=""]');
        if (rootFolder) {
            rootFolder.addEventListener('click', () => {
                this.navigateToFolder('');
            });
        }
    }

    // File Upload
    handleFileSelect(files) {
        if (!files || files.length === 0) return;
        this.uploadFiles(Array.from(files));
    }

    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropZone.classList.add('drop-zone-active');
    }

    handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropZone.classList.remove('drop-zone-active');
    }

    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropZone.classList.remove('drop-zone-active');

        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            this.uploadFiles(files);
        }
    }

    async uploadFiles(files) {
        this.uploadProgress.classList.remove('hidden');
        this.uploadProgress.innerHTML = '';

        this.showMessage(`Uploading ${files.length} file(s)...`, 'info');

        for (const file of files) {
            await this.uploadFile(file);
        }

        setTimeout(() => {
            this.uploadProgress.classList.add('hidden');
            this.uploadProgress.innerHTML = '';
        }, 2000);
    }

    async uploadFile(file) {
        const progressItem = this.createProgressItem(file.name);
        this.uploadProgress.appendChild(progressItem);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('folder', this.currentPath);

        try {
            const response = await this.authenticatedFetch(this.buildUrl('/upload'), {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                this.updateProgressItem(progressItem, 100, 'success');
                this.showMessage(`${file.name} uploaded successfully`, 'success');
                this.navigateToFolder(this.currentPath);
            } else {
                this.updateProgressItem(progressItem, 0, 'error');
                this.showMessage(data.error || `Failed to upload ${file.name}`, 'error');
            }
        } catch (error) {
            this.updateProgressItem(progressItem, 0, 'error');
            this.showMessage(`Failed to upload ${file.name}`, 'error');
        }
    }

    createProgressItem(filename) {
        const item = document.createElement('div');
        item.className = 'bg-white border rounded-lg p-3';
        item.innerHTML = `
            <div class="flex items-center space-x-3">
                <div class="flex-shrink-0">
                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-gray-900 truncate">${filename}</p>
                    <div class="mt-1 w-full bg-gray-200 rounded-full h-2">
                        <div class="progress-bar bg-blue-600 h-2 rounded-full" style="width: 0%"></div>
                    </div>
                </div>
                <div class="flex-shrink-0">
                    <span class="progress-percent text-sm text-gray-500">0%</span>
                </div>
            </div>
        `;
        return item;
    }

    updateProgressItem(item, percent, status = 'progress') {
        const progressBar = item.querySelector('.progress-bar');
        const progressPercent = item.querySelector('.progress-percent');
        const spinner = item.querySelector('.animate-spin');

        if (progressBar) progressBar.style.width = `${percent}%`;
        if (progressPercent) progressPercent.textContent = `${percent}%`;

        if (status === 'success' && spinner) {
            spinner.innerHTML = '<i class="fas fa-check-circle text-green-500"></i>';
            spinner.classList.remove('animate-spin', 'border-b-2', 'border-blue-600');
        } else if (status === 'error' && spinner) {
            spinner.innerHTML = '<i class="fas fa-times-circle text-red-500"></i>';
            spinner.classList.remove('animate-spin', 'border-b-2', 'border-blue-600');
        }
    }

    // Folder Navigation
    async navigateToFolder(path) {
        this.currentPath = path;
        this.clearSelection();
        this.updateBreadcrumb();
        this.updateFolderTreeSelection();
        await this.loadFiles();
    }

    async loadFiles() {
        try {
            const response = await fetch(this.buildUrl(`/list?prefix=${encodeURIComponent(this.currentPath)}`));
            const data = await response.json();

            if (data.error) {
                this.showMessage(data.error, 'error');
                return;
            }

            this.renderFiles(data.files || []);
        } catch (error) {
            this.showMessage('Failed to load files', 'error');
            console.error('Load files error:', error);
        }
    }

    async loadFolderStructure() {
        try {
            // Load only root-level folders initially
            const response = await fetch(this.buildUrl('/list?prefix='));
            const data = await response.json();

            if (data.files) {
                console.log('Loading root folder structure from files:', data.files);
                this.buildRootFolderStructure(data.files);
                this.renderFolderTree();
            }
        } catch (error) {
            console.error('Failed to load folder structure:', error);
        }
    }

    async loadSubfolders(folderPath) {
        try {
            // Fetch contents of a specific folder
            const response = await fetch(this.buildUrl(`/list?prefix=${encodeURIComponent(folderPath)}`));
            const data = await response.json();

            if (data.files) {
                console.log(`Loading subfolders for ${folderPath}:`, data.files);
                return data.files;
            }
            return [];
        } catch (error) {
            console.error(`Failed to load subfolders for ${folderPath}:`, error);
            return [];
        }
    }

    buildRootFolderStructure(files) {
        this.folderStructure = {};
        const rootFolders = new Set();

        console.log('buildRootFolderStructure received', files.length, 'files');

        files.forEach(file => {
            // Detect folders: type='folder', mime_type='folder', size=0 with null mime_type, or ends with '/'
            const isFolder = file.type === 'folder' ||
                file.mime_type === 'folder' ||
                file.name.endsWith('/') ||
                (file.size === 0 && (file.mime_type === null || file.mime_type === undefined));

            console.log('Processing file:', file.name, 'isFolder:', isFolder, 'type:', file.type, 'mime_type:', file.mime_type, 'size:', file.size);

            let pathToProcess = file.name;

            if (!isFolder && pathToProcess.includes('/')) {
                // Extract the root folder from file path
                // "hello/file.txt" -> "hello/"
                const firstSlashIndex = pathToProcess.indexOf('/');
                pathToProcess = pathToProcess.substring(0, firstSlashIndex + 1);
            } else if (isFolder) {
                // Ensure folder path ends with /
                pathToProcess = pathToProcess.endsWith('/') ? pathToProcess : pathToProcess + '/';

                // Only take the root-level folder
                const firstSlashIndex = pathToProcess.indexOf('/');
                const secondSlashIndex = pathToProcess.indexOf('/', firstSlashIndex + 1);
                if (secondSlashIndex !== -1) {
                    // This is a subfolder, extract only the root part
                    pathToProcess = pathToProcess.substring(0, secondSlashIndex + 1);
                }
            } else {
                // Root level file, skip
                return;
            }

            // Extract root folder name (remove trailing slash)
            const folderName = pathToProcess.replace(/\/$/, '');
            if (folderName && !rootFolders.has(folderName)) {
                rootFolders.add(folderName);
                console.log('Adding root folder:', folderName, 'with path:', folderName + '/');
                this.folderStructure[folderName] = {
                    name: folderName,
                    path: folderName + '/',
                    children: null, // null means not loaded yet, {} means loaded but empty
                    loaded: false
                };
            }
        });

        console.log('Root folder structure built:', this.folderStructure);
    }

    async buildSubfolderStructure(folderPath, files) {
        // Find the folder node in the structure
        const parts = folderPath.replace(/\/$/, '').split('/').filter(p => p);
        let current = this.folderStructure;

        // Navigate to the folder node
        for (const part of parts) {
            if (!current[part]) return;
            current = current[part];
            if (current.children) {
                current = current.children;
            }
        }

        // Now 'current' is the folder node, initialize its children
        if (!current.children || current.children === null) {
            current.children = {};
        }

        const subfolders = new Set();

        files.forEach(file => {
            // Detect folders: type='folder', mime_type='folder', size=0 with null mime_type, or ends with '/'
            const isFolder = file.type === 'folder' ||
                file.mime_type === 'folder' ||
                file.name.endsWith('/') ||
                (file.size === 0 && (file.mime_type === null || file.mime_type === undefined));

            // Remove the current folder prefix
            let relativePath = file.name;
            if (relativePath.startsWith(folderPath)) {
                relativePath = relativePath.substring(folderPath.length);
            }

            if (!relativePath || relativePath === '') return;

            if (!isFolder && relativePath.includes('/')) {
                // Extract the immediate subfolder from file path
                const firstSlashIndex = relativePath.indexOf('/');
                relativePath = relativePath.substring(0, firstSlashIndex + 1);
            } else if (isFolder) {
                // Ensure folder path ends with /
                relativePath = relativePath.endsWith('/') ? relativePath : relativePath + '/';

                // Only take the immediate subfolder
                const firstSlashIndex = relativePath.indexOf('/');
                const secondSlashIndex = relativePath.indexOf('/', firstSlashIndex + 1);
                if (secondSlashIndex !== -1) {
                    // This is a deeper subfolder, extract only the immediate part
                    relativePath = relativePath.substring(0, secondSlashIndex + 1);
                }
            } else {
                // File in current folder, skip
                return;
            }

            // Extract subfolder name
            const subfolderName = relativePath.replace(/\/$/, '');
            if (subfolderName && !subfolders.has(subfolderName)) {
                subfolders.add(subfolderName);
                current.children[subfolderName] = {
                    name: subfolderName,
                    path: folderPath + subfolderName + '/',
                    children: null,
                    loaded: false
                };
            }
        });

        current.loaded = true;
        console.log(`Subfolders built for ${folderPath}:`, current.children);
    }

    renderFolderTree() {
        const tree = this.folderTree.querySelector('.folder-tree-item[data-path=""]');
        if (!tree) {
            console.error('Root folder tree item not found!');
            return;
        }

        console.log('Rendering folder tree with structure:', this.folderStructure);

        const renderNode = (node, level = 0) => {
            const container = document.createElement('div');

            Object.values(node).forEach(folder => {
                // Check if this folder has children or might have children (not loaded yet)
                const hasChildren = folder.children && Object.keys(folder.children).length > 0;
                const mightHaveChildren = folder.children === null || hasChildren;

                // Create folder item container
                const itemWrapper = document.createElement('div');
                itemWrapper.className = 'folder-tree-wrapper';
                itemWrapper.dataset.path = folder.path;

                // Create the folder item
                const item = document.createElement('div');
                item.className = 'folder-tree-item flex items-center';
                item.style.paddingLeft = `${level * 1}rem`;
                item.dataset.path = folder.path;

                // Expand/collapse icon (show if has or might have children)
                const expandIcon = document.createElement('i');
                if (mightHaveChildren) {
                    expandIcon.className = 'fas fa-chevron-right mr-1 text-xs text-gray-500 cursor-pointer expand-icon';
                    expandIcon.style.width = '12px';
                    expandIcon.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        await this.toggleFolderExpansion(itemWrapper);
                    });
                } else {
                    expandIcon.style.width = '12px';
                    expandIcon.style.marginRight = '0.25rem';
                }

                // Folder icon
                const folderIcon = document.createElement('i');
                folderIcon.className = 'fas fa-folder mr-2 text-yellow-500';

                // Folder name
                const folderName = document.createElement('span');
                folderName.textContent = folder.name;
                folderName.className = 'cursor-pointer flex-1';
                folderName.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.navigateToFolder(folder.path);
                });

                item.appendChild(expandIcon);
                item.appendChild(folderIcon);
                item.appendChild(folderName);
                itemWrapper.appendChild(item);

                // Add children container (initially hidden)
                if (hasChildren) {
                    const childrenContainer = document.createElement('div');
                    childrenContainer.className = 'folder-children hidden';
                    childrenContainer.appendChild(renderNode(folder.children, level + 1));
                    itemWrapper.appendChild(childrenContainer);
                } else if (mightHaveChildren) {
                    // Create empty children container for lazy loading
                    const childrenContainer = document.createElement('div');
                    childrenContainer.className = 'folder-children hidden';
                    itemWrapper.appendChild(childrenContainer);
                }

                container.appendChild(itemWrapper);
            });

            return container;
        };

        // Remove old folders (but keep the root folder item)
        this.folderTree.querySelectorAll('.folder-tree-wrapper').forEach(el => el.remove());

        // Add new folders
        if (Object.keys(this.folderStructure).length > 0) {
            const folderNodes = renderNode(this.folderStructure);
            this.folderTree.appendChild(folderNodes);
            console.log('Folder tree rendered successfully with', Object.keys(this.folderStructure).length, 'root folders');
        } else {
            console.log('No folders to display in tree');
        }
    }

    async toggleFolderExpansion(folderWrapper) {
        const expandIcon = folderWrapper.querySelector('.expand-icon');
        const childrenContainer = folderWrapper.querySelector('.folder-children');
        const folderPath = folderWrapper.dataset.path;

        if (!childrenContainer) return;

        const isExpanded = !childrenContainer.classList.contains('hidden');

        if (isExpanded) {
            // Collapse
            childrenContainer.classList.add('hidden');
            expandIcon.classList.remove('fa-chevron-down');
            expandIcon.classList.add('fa-chevron-right');
        } else {
            // Expand - load subfolders if not loaded yet
            const parts = folderPath.replace(/\/$/, '').split('/').filter(p => p);
            let folderNode = this.folderStructure;

            // Navigate to the folder node
            for (const part of parts) {
                if (!folderNode[part]) return;
                folderNode = folderNode[part];
                if (folderNode.children && typeof folderNode.children === 'object') {
                    folderNode = folderNode.children;
                }
            }

            // Load subfolders if not loaded yet
            if (!folderNode.loaded) {
                console.log(`Loading subfolders for ${folderPath}...`);
                const files = await this.loadSubfolders(folderPath);
                await this.buildSubfolderStructure(folderPath, files);
                this.renderFolderTree();

                // Re-select the folder after re-rendering
                this.updateFolderTreeSelection();
            }

            childrenContainer.classList.remove('hidden');
            expandIcon.classList.remove('fa-chevron-right');
            expandIcon.classList.add('fa-chevron-down');
        }
    }

    updateFolderTreeSelection() {
        this.folderTree.querySelectorAll('.folder-tree-item').forEach(item => {
            item.classList.remove('active');
        });

        // Find and highlight the active folder
        const activeWrapper = this.folderTree.querySelector(`.folder-tree-wrapper[data-path="${this.currentPath}"]`);
        if (activeWrapper) {
            const activeItem = activeWrapper.querySelector('.folder-tree-item');
            if (activeItem) {
                activeItem.classList.add('active');
            }

            // Auto-expand parent folders
            this.expandParentFolders(activeWrapper);
        }
    }

    expandParentFolders(targetWrapper) {
        // Find all parent folder wrappers and expand them
        let current = targetWrapper.parentElement;
        while (current && current !== this.folderTree) {
            if (current.classList.contains('folder-children')) {
                // This is a children container, find its wrapper
                const parentWrapper = current.closest('.folder-tree-wrapper');
                if (parentWrapper) {
                    const expandIcon = parentWrapper.querySelector('.expand-icon');
                    const childrenContainer = parentWrapper.querySelector('.folder-children');

                    if (childrenContainer && expandIcon) {
                        // Expand if not already expanded
                        if (childrenContainer.classList.contains('hidden')) {
                            childrenContainer.classList.remove('hidden');
                            expandIcon.classList.remove('fa-chevron-right');
                            expandIcon.classList.add('fa-chevron-down');
                        }
                    }
                }
            }
            current = current.parentElement;
        }
    }

    updateBreadcrumb() {
        const parts = this.currentPath.split('/').filter(p => p);

        let html = `
            <button class="breadcrumb-item hover:text-blue-600 transition" data-path="">
                <i class="fas fa-home mr-1"></i>Home
            </button>
        `;

        let path = '';
        parts.forEach((part) => {
            path += part + '/';
            html += `
                <span class="breadcrumb-separator">/</span>
                <button class="breadcrumb-item hover:text-blue-600 transition" data-path="${path}">
                    ${part}
                </button>
            `;
        });

        this.breadcrumb.innerHTML = html;

        this.breadcrumb.querySelectorAll('.breadcrumb-item').forEach(btn => {
            btn.addEventListener('click', () => this.navigateToFolder(btn.dataset.path));
        });
    }

    // Render Files
    renderFiles(files) {
        if (files.length === 0) {
            this.fileList.classList.add('hidden');
            this.emptyState.classList.remove('hidden');
            this.dropZone.classList.remove('hidden');
            return;
        }

        this.fileList.classList.remove('hidden');
        this.emptyState.classList.add('hidden');
        this.dropZone.classList.add('hidden');

        // Separate folders and files
        const folders = files.filter(f =>
            f.type === 'folder' ||
            f.mime_type === 'folder' ||
            f.name.endsWith('/') ||
            (f.size === 0 && (f.mime_type === null || f.mime_type === undefined))
        );
        const regularFiles = files.filter(f =>
            f.type === 'file' &&
            !f.name.endsWith('/') &&
            !(f.size === 0 && (f.mime_type === null || f.mime_type === undefined))
        );

        const allItems = [...folders, ...regularFiles];

        this.fileList.innerHTML = allItems.map(item => {
            const isFolder = item.type === 'folder' ||
                item.mime_type === 'folder' ||
                item.name.endsWith('/') ||
                (item.size === 0 && (item.mime_type === null || item.mime_type === undefined));
            const displayName = isFolder ? item.name.replace(/\/$/, '').split('/').pop() : item.name.split('/').pop();
            const fullPath = item.name;

            return this.viewMode === 'grid'
                ? this.renderGridItem(displayName, fullPath, item, isFolder)
                : this.renderListItem(displayName, fullPath, item, isFolder);
        }).join('');

        // Attach event listeners
        this.fileList.querySelectorAll('.file-item').forEach(item => {
            item.addEventListener('click', (e) => this.handleItemClick(e, item));
            item.addEventListener('dblclick', () => this.handleItemDoubleClick(item));
            item.addEventListener('contextmenu', (e) => this.handleContextMenu(e, item));
        });
    }

    renderGridItem(name, path, item, isFolder) {
        const icon = this.getFileIcon(item.mime_type, isFolder);
        const size = isFolder ? '' : this.formatFileSize(item.size);

        return `
            <div class="file-item bg-white border rounded-lg p-4 text-center hover:shadow-md"
                 data-path="${path}"
                 data-is-folder="${isFolder}">
                <div class="mb-2">
                    ${icon}
                </div>
                <div class="text-sm font-medium text-gray-900 truncate" title="${name}">${name}</div>
                ${size ? `<div class="text-xs text-gray-500 mt-1">${size}</div>` : ''}
            </div>
        `;
    }

    renderListItem(name, path, item, isFolder) {
        const icon = this.getFileIcon(item.mime_type, isFolder, 'small');
        const size = isFolder ? '--' : this.formatFileSize(item.size);

        return `
            <div class="file-item bg-white border rounded-lg p-3 flex items-center justify-between hover:shadow-md mb-2"
                 data-path="${path}"
                 data-is-folder="${isFolder}">
                <div class="flex items-center flex-1 min-w-0">
                    <div class="flex-shrink-0 mr-3">${icon}</div>
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-medium text-gray-900 truncate">${name}</div>
                    </div>
                </div>
                <div class="flex-shrink-0 ml-4 text-sm text-gray-500">${size}</div>
            </div>
        `;
    }

    getFileIcon(mimeType, isFolder, size = 'large') {
        const iconSize = size === 'large' ? 'text-5xl' : 'text-2xl';

        if (isFolder) {
            return `<i class="fas fa-folder ${iconSize} text-yellow-500"></i>`;
        }

        if (!mimeType) {
            return `<i class="fas fa-file ${iconSize} text-gray-400"></i>`;
        }

        if (mimeType.startsWith('image/')) {
            return `<i class="fas fa-file-image ${iconSize} text-purple-500"></i>`;
        } else if (mimeType.startsWith('video/')) {
            return `<i class="fas fa-file-video ${iconSize} text-pink-500"></i>`;
        } else if (mimeType === 'application/pdf') {
            return `<i class="fas fa-file-pdf ${iconSize} text-red-500"></i>`;
        } else if (mimeType.includes('zip') || mimeType.includes('archive')) {
            return `<i class="fas fa-file-archive ${iconSize} text-orange-500"></i>`;
        } else if (mimeType.includes('word') || mimeType.includes('document')) {
            return `<i class="fas fa-file-word ${iconSize} text-blue-500"></i>`;
        } else if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) {
            return `<i class="fas fa-file-excel ${iconSize} text-green-500"></i>`;
        }

        return `<i class="fas fa-file ${iconSize} text-gray-400"></i>`;
    }

    formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Item Interaction
    handleItemClick(e, item) {
        if (e.ctrlKey || e.metaKey) {
            this.toggleItemSelection(item);
        } else if (e.shiftKey && this.selectedItems.size > 0) {
            this.selectRange(item);
        } else {
            this.clearSelection();
            this.selectItem(item);
        }

        this.updateActionButtons();
    }

    handleItemDoubleClick(item) {
        const isFolder = item.dataset.isFolder === 'true';
        const path = item.dataset.path;

        if (isFolder) {
            this.navigateToFolder(path);
        } else {
            this.openFile(path);
        }
    }

    handleContextMenu(e, item) {
        e.preventDefault();

        if (!item.classList.contains('selected')) {
            this.clearSelection();
            this.selectItem(item);
        }

        this.showContextMenu(e.clientX, e.clientY, item);
    }

    // Selection
    selectItem(item) {
        item.classList.add('selected');
        this.selectedItems.add(item.dataset.path);
    }

    toggleItemSelection(item) {
        if (item.classList.contains('selected')) {
            item.classList.remove('selected');
            this.selectedItems.delete(item.dataset.path);
        } else {
            this.selectItem(item);
        }
    }

    clearSelection() {
        this.fileList.querySelectorAll('.file-item.selected').forEach(item => {
            item.classList.remove('selected');
        });
        this.selectedItems.clear();
        this.updateActionButtons();
    }

    toggleSelectAll() {
        const items = this.fileList.querySelectorAll('.file-item');
        const allSelected = items.length === this.selectedItems.size;

        if (allSelected) {
            this.clearSelection();
        } else {
            items.forEach(item => this.selectItem(item));
        }

        this.updateActionButtons();
    }

    updateActionButtons() {
        const hasSelection = this.selectedItems.size > 0;
        this.deleteBtn.disabled = !hasSelection;
        this.downloadBtn.disabled = !hasSelection;
        this.shareBtn.disabled = !hasSelection;
    }

    // Context Menu
    showContextMenu(x, y, item) {
        this.contextMenu.style.left = x + 'px';
        this.contextMenu.style.top = y + 'px';
        this.contextMenu.classList.add('active');
        this.contextMenu.dataset.targetPath = item.dataset.path;
        this.contextMenu.dataset.isFolder = item.dataset.isFolder;
    }

    hideContextMenu() {
        this.contextMenu.classList.remove('active');
    }

    handleContextMenuAction(e) {
        const action = e.target.closest('.context-menu-item')?.dataset.action;
        if (!action) return;

        const path = this.contextMenu.dataset.targetPath;
        const isFolder = this.contextMenu.dataset.isFolder === 'true';

        this.hideContextMenu();

        switch (action) {
            case 'open':
                if (isFolder) {
                    this.navigateToFolder(path);
                } else {
                    this.openFile(path);
                }
                break;
            case 'download':
                this.downloadFile(path);
                break;
            case 'share':
                this.shareFile(path);
                break;
            case 'rename':
                this.renameItem(path);
                break;
            case 'delete':
                this.deleteFile(path);
                break;
        }
    }

    // File Operations
    async openFile(path) {
        try {
            const response = await fetch(this.buildUrl(`/share/${encodeURIComponent(path)}`));
            const data = await response.json();

            if (data.preview_url) {
                this.showPreviewModal(data.preview_url, data.mime_type, path);
            } else {
                this.downloadFile(path);
            }
        } catch (error) {
            this.showMessage('Failed to open file', 'error');
        }
    }

    showPreviewModal(url, mimeType, filename) {
        this.previewTitle.textContent = filename;

        if (mimeType?.startsWith('image/')) {
            this.previewContent.innerHTML = `<img src="${url}" class="max-w-full h-auto mx-auto">`;
        } else if (mimeType === 'application/pdf') {
            this.previewContent.innerHTML = `<iframe src="${url}" class="w-full h-[600px]"></iframe>`;
        } else if (mimeType?.startsWith('video/')) {
            this.previewContent.innerHTML = `<video src="${url}" controls class="max-w-full h-auto mx-auto"></video>`;
        } else {
            this.previewContent.innerHTML = '<div class="text-center text-gray-500">Preview not available</div>';
        }

        this.previewModal.classList.remove('hidden');
        this.previewModal.classList.add('flex');
    }

    closePreviewModal() {
        this.previewModal.classList.add('hidden');
        this.previewModal.classList.remove('flex');
        this.previewContent.innerHTML = '';
    }

    async downloadFile(path) {
        window.location.href = this.buildUrl(`/download/${encodeURIComponent(path)}`);
    }

    async shareFile(path) {
        try {
            const response = await fetch(this.buildUrl(`/share/${encodeURIComponent(path)}`));
            const data = await response.json();

            if (data.url) {
                await navigator.clipboard.writeText(data.url);
                this.showMessage('Share link copied to clipboard!', 'success');
            }
        } catch (error) {
            this.showMessage('Failed to generate share link', 'error');
        }
    }

    async deleteFile(path) {
        if (!confirm(`Are you sure you want to delete "${path}"?`)) return;

        try {
            const response = await this.authenticatedFetch(this.buildUrl(`/delete/${encodeURIComponent(path)}`), {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showMessage('Deleted successfully', 'success');
                this.navigateToFolder(this.currentPath);
                this.loadFolderStructure();
            } else {
                const data = await response.json();
                this.showMessage(data.error || 'Delete failed', 'error');
            }
        } catch (error) {
            this.showMessage('Delete failed', 'error');
        }
    }

    async deleteSelected() {
        if (this.selectedItems.size === 0) return;

        if (!confirm(`Delete ${this.selectedItems.size} item(s)?`)) return;

        for (const path of this.selectedItems) {
            await this.deleteFile(path);
        }
    }

    async downloadSelected() {
        for (const path of this.selectedItems) {
            await this.downloadFile(path);
        }
    }

    async shareSelected() {
        if (this.selectedItems.size === 1) {
            await this.shareFile(Array.from(this.selectedItems)[0]);
        } else {
            this.showMessage('Please select only one file to share', 'info');
        }
    }

    async createNewFolder() {
        const folderName = prompt('Enter folder name:');
        if (!folderName) return;

        try {
            const response = await this.authenticatedFetch(this.buildUrl('/create_folder'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    folder_name: this.currentPath + folderName + '/'
                })
            });

            if (response.ok) {
                this.showMessage('Folder created successfully', 'success');
                this.navigateToFolder(this.currentPath);
                this.loadFolderStructure();
            } else {
                const data = await response.json();
                this.showMessage(data.error || 'Failed to create folder', 'error');
            }
        } catch (error) {
            this.showMessage('Failed to create folder', 'error');
        }
    }

    // View Mode
    setViewMode(mode) {
        this.viewMode = mode;

        this.gridViewBtn.classList.toggle('active', mode === 'grid');
        this.listViewBtn.classList.toggle('active', mode === 'list');

        if (mode === 'grid') {
            this.fileList.className = 'file-explorer-grid';
        } else {
            this.fileList.className = 'space-y-2';
        }

        this.loadFiles();
    }

    // Keyboard Shortcuts
    handleKeyboard(e) {
        // Ctrl+A or Cmd+A - Select All
        if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
            e.preventDefault();
            this.toggleSelectAll();
        }

        // Delete - Delete selected
        if (e.key === 'Delete') {
            this.deleteSelected();
        }

        // Escape - Clear selection
        if (e.key === 'Escape') {
            this.clearSelection();
            this.closePreviewModal();
        }
    }

    async refreshCsrfToken() {
        try {
            const response = await fetch(this.buildUrl('/get-csrf-token'));
            const data = await response.json();
            if (data.csrf_token) {
                this.csrfToken = data.csrf_token;
                // Update meta tag for consistency
                const meta = document.querySelector('meta[name="csrf-token"]');
                if (meta) meta.setAttribute('content', data.csrf_token);
                return true;
            }
        } catch (error) {
            console.error('Error fetching CSRF token:', error);
        }
        return false;
    }

    // Wrap fetch to handle CSRF token refresh
    async authenticatedFetch(url, options = {}) {
        if (!options.headers) options.headers = {};
        if (options.method && options.method !== 'GET') {
            options.headers['X-CSRFToken'] = this.csrfToken;
        }

        let response = await fetch(url, options);

        // If CSRF token mismatch/missing, refresh and retry once
        if (response.status === 403) {
            const data = await response.clone().json().catch(() => ({}));
            if (data.error && data.error.toLowerCase().includes('csrf')) {
                console.warn('CSRF error detected, refreshing token and retrying...');
                const refreshed = await this.refreshCsrfToken();
                if (refreshed) {
                    options.headers['X-CSRFToken'] = this.csrfToken;
                    response = await fetch(url, options);
                }
            }
        }

        return response;
    }

    // Utilities
    showMessage(message, type = 'info') {
        const bgColor = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            info: 'bg-blue-500'
        }[type] || 'bg-gray-500';

        const messageDiv = document.createElement('div');
        messageDiv.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg ${bgColor} text-white shadow-lg z-50 transition-opacity`;
        messageDiv.innerHTML = `
            <div class="flex items-center space-x-2">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;

        document.body.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.style.opacity = '0';
            setTimeout(() => messageDiv.remove(), 300);
        }, 3000);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.fileExplorer = new FileExplorer();
});
