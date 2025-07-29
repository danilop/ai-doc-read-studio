class DocReadStudio {
    constructor() {
        this.apiUrl = window.APP_CONFIG ? window.APP_CONFIG.API_BASE_URL : 'http://localhost:8000';
        this.documents = []; // Array to store multiple documents
        this.sessionId = null;
        this.teamMembers = [];
        this.memberCounter = 0;
        this.maxDocuments = 10;
        this.websocket = null;
        this.websocketReconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.lastVersionCheck = null;
        this.buttonHandlers = {};
        this.currentEnterHandler = null;
        
        // Get model configuration from config file
        this.modelOptions = window.APP_CONFIG?.models?.available || [
            { value: 'nova-lite', label: 'Lite (Balanced)', description: 'Balanced' }
        ];
        this.defaultTeamModel = window.APP_CONFIG?.models?.default_team || 'nova-lite';
        this.defaultSummaryModel = window.APP_CONFIG?.models?.default_summary || 'nova-lite';
        
        // Initialize logging
        this.initializeLogging();
        
        // Verify DOM structure is correct
        this.verifyDOMStructure();
        
        this.initializeEventListeners();
        this.addDefaultTeamMembers();
        this.initializeModelSelectors();
        
        // Start version checking
        this.startVersionChecking();
    }
    
    generateModelOptionsHtml(selectedValue = null, useTeamDefault = true) {
        const defaultValue = useTeamDefault ? this.defaultTeamModel : this.defaultSummaryModel;
        
        // Model icons matching the indicator badges
        const modelIcons = {
            'nova-micro': '⚪',
            'nova-lite': '🔵',
            'nova-pro': '🟠',
            'nova-premier': '🟣'
        };
        
        return this.modelOptions.map(option => {
            const selected = (selectedValue === option.value || 
                            (!selectedValue && option.value === defaultValue)) ? 'selected' : '';
            const icon = modelIcons[option.value] || '🔸';
            return `<option value="${option.value}" ${selected}>${icon} ${option.label}</option>`;
        }).join('');
    }
    
    initializeModelSelectors() {
        // Initialize summary model selector with configured default
        const summaryModelSelect = document.getElementById('summaryModelSelect');
        if (summaryModelSelect) {
            summaryModelSelect.innerHTML = this.generateModelOptionsHtml(null, false);
        }
    }
    
    // WebSocket connection methods
    connectWebSocket(sessionId) {
        if (this.websocket) {
            this.disconnectWebSocket();
        }
        
        const wsUrl = this.apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');
        const websocketUrl = sessionId ? `${wsUrl}/ws/${sessionId}` : `${wsUrl}/ws`;
        
        try {
            this.websocket = new WebSocket(websocketUrl);
            
            this.websocket.onopen = () => {
                this.log('info', 'WebSocket connected', { sessionId });
                this.websocketReconnectAttempts = 0;
                
                // Send ping to keep connection alive
                setInterval(() => {
                    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                        this.websocket.send(JSON.stringify({ type: 'ping' }));
                    }
                }, 30000); // Ping every 30 seconds
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (e) {
                    this.log('error', 'Failed to parse WebSocket message', { error: e.message, data: event.data });
                }
            };
            
            this.websocket.onclose = (event) => {
                this.log('info', 'WebSocket disconnected', { code: event.code, reason: event.reason });
                this.websocket = null;
                
                // Attempt to reconnect if session is active
                if (this.sessionId && this.websocketReconnectAttempts < this.maxReconnectAttempts) {
                    this.websocketReconnectAttempts++;
                    this.log('info', 'Attempting WebSocket reconnection', { attempt: this.websocketReconnectAttempts });
                    setTimeout(() => {
                        this.connectWebSocket(this.sessionId);
                    }, 2000 * this.websocketReconnectAttempts); // Exponential backoff
                }
            };
            
            this.websocket.onerror = (error) => {
                this.log('error', 'WebSocket error', { error: error.toString() });
            };
            
        } catch (error) {
            this.log('error', 'Failed to create WebSocket connection', { error: error.message });
        }
    }
    
    disconnectWebSocket() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
            this.log('info', 'WebSocket disconnected manually');
        }
    }
    
    handleWebSocketMessage(message) {
        this.log('debug', 'Received WebSocket message', { type: message.type });
        
        switch (message.type) {
            case 'agent_response':
                this.handleRealtimeAgentResponse(message.data);
                break;
            case 'agent_thinking':
                // Show individual agent thinking with typing bubble
                this.showAgentTyping(message.data.agent_name);
                this.log('debug', 'Agent thinking started', { agent: message.data.agent_name });
                break;
            case 'agent_finished':
                // Remove individual agent thinking bubble
                this.removeAgentTyping(message.data.agent_name);
                this.log('debug', 'Agent thinking finished', { agent: message.data.agent_name });
                break;
            case 'session_info':
                this.log('info', 'Received session info', message);
                break;
            case 'pong':
                // Response to ping, connection is alive
                break;
            case 'echo':
                this.log('debug', 'WebSocket echo received', message);
                break;
            default:
                this.log('debug', 'Unknown WebSocket message type', message);
        }
    }
    
    handleRealtimeAgentResponse(agentResponse) {
        // Only add to conversation if this is a new response
        const conversationDiv = document.getElementById('conversation');
        const existingMessages = conversationDiv.querySelectorAll('.message.agent');
        
        // Check if this response is already displayed by comparing timestamp and agent
        let isNewResponse = true;
        existingMessages.forEach(msg => {
            const timestamp = msg.querySelector('.message-meta')?.textContent;
            const agentName = msg.querySelector('.message-header span')?.textContent;
            if (timestamp && agentName === agentResponse.agent_name) {
                const msgTime = new Date(timestamp).getTime();
                const responseTime = new Date(agentResponse.timestamp).getTime();
                if (Math.abs(msgTime - responseTime) < 1000) { // Within 1 second
                    isNewResponse = false;
                }
            }
        });
        
        if (isNewResponse) {
            // Remove any typing indicator for this agent
            this.removeAgentTyping(agentResponse.agent_name);
            
            // Add the response with animation
            this.addMessageToConversation(agentResponse, true);
            
            this.log('info', 'Added real-time agent response', { 
                agent: agentResponse.agent_name, 
                length: agentResponse.content.length 
            });
        }
    }
    
    setEnterKeyHandler(handler) {
        // Clean approach: use a single handler with dynamic behavior
        const promptInput = document.getElementById('promptInput');
        if (promptInput) {
            // Remove existing handlers
            promptInput.removeEventListener('keydown', this.currentEnterHandler);
            
            // Create new handler
            this.currentEnterHandler = (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handler();
                }
            };
            
            // Add new handler
            promptInput.addEventListener('keydown', this.currentEnterHandler);
        }
    }
    
    setButtonHandler(buttonId, handler, text = null) {
        // Clean button handler setter without DOM manipulation
        const button = document.getElementById(buttonId);
        if (button) {
            // Remove existing handler if stored
            if (this.buttonHandlers && this.buttonHandlers[buttonId]) {
                button.removeEventListener('click', this.buttonHandlers[buttonId]);
            }
            
            // Initialize handlers storage
            if (!this.buttonHandlers) this.buttonHandlers = {};
            
            // Store and add new handler
            this.buttonHandlers[buttonId] = handler;
            button.addEventListener('click', handler);
            
            // Update text if provided
            if (text) {
                button.textContent = text;
            }
        }
    }
    
    verifyDOMStructure() {
        // Comprehensive DOM structure verification
        const mainContent = document.getElementById('mainContent');
        const sidebar = document.getElementById('sidebarContainer');
        const discussionArea = document.querySelector('.discussion-area');
        // const promptInput = document.getElementById('promptInput'); // Currently unused in verification
        const conversation = document.getElementById('conversation');
        
        console.log('🔍 COMPREHENSIVE DOM STRUCTURE VERIFICATION...');
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        
        // Main content analysis
        console.log('📋 Main Content Analysis:');
        if (mainContent) {
            console.log(`  • Children count: ${mainContent.children.length} (should be 2)`);
            console.log('  • Children details:');
            for (let i = 0; i < mainContent.children.length; i++) {
                const child = mainContent.children[i];
                console.log(`    ${i + 1}. ${child.tagName} class="${child.className}" id="${child.id}"`);
            }
        } else {
            console.error('  ❌ Main content NOT FOUND');
        }
        
        // Sidebar analysis
        console.log('📋 Sidebar Analysis:');
        if (sidebar) {
            console.log(`  • Parent: ${sidebar.parentElement?.id || 'no id'} (should be mainContent)`);
            console.log(`  • Grid column: ${getComputedStyle(sidebar).gridColumn}`);
        } else {
            console.error('  ❌ Sidebar NOT FOUND');
        }
        
        // Discussion area analysis
        console.log('📋 Discussion Area Analysis:');
        if (discussionArea) {
            console.log(`  • Parent: ${discussionArea.parentElement?.id || 'no id'} (should be mainContent)`);
            console.log(`  • Grid column: ${getComputedStyle(discussionArea).gridColumn}`);
            console.log(`  • Children count: ${discussionArea.children.length}`);
        } else {
            console.error('  ❌ Discussion area NOT FOUND');
        }
        
        // Conversation element analysis
        console.log('📋 Conversation Element Analysis:');
        if (conversation) {
            console.log(`  • Parent: ${conversation.parentElement?.className || 'no class'}`);
            console.log(`  • Grandparent: ${conversation.parentElement?.parentElement?.id || 'no id'}`);
        } else {
            console.error('  ❌ Conversation element NOT FOUND');
        }
        
        // Check for duplicates
        console.log('📋 Duplicate Check:');
        const allConversationElements = document.querySelectorAll('.conversation');
        const allDiscussionElements = document.querySelectorAll('.discussion-area');
        console.log(`  • Conversation elements found: ${allConversationElements.length} (should be 1)`);
        console.log(`  • Discussion areas found: ${allDiscussionElements.length} (should be 1)`);
        
        // Error summary
        const errors = [];
        if (mainContent && mainContent.children.length !== 2) {
            errors.push(`Main content has ${mainContent.children.length} children (should be 2)`);
        }
        if (discussionArea && discussionArea.parentElement !== mainContent) {
            errors.push('Discussion area parent is not main-content');
        }
        if (sidebar && sidebar.parentElement !== mainContent) {
            errors.push('Sidebar parent is not main-content');
        }
        if (allConversationElements.length !== 1) {
            errors.push(`Found ${allConversationElements.length} conversation elements`);
        }
        if (allDiscussionElements.length !== 1) {
            errors.push(`Found ${allDiscussionElements.length} discussion areas`);
        }
        
        if (errors.length > 0) {
            console.error('❌ ERRORS DETECTED:');
            errors.forEach(error => console.error(`  • ${error}`));
        } else {
            console.log('✅ DOM structure appears correct');
        }
        
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    }

    // ============================================================================
    // UTILITY METHODS - DRY PRINCIPLE REFACTORING
    // ============================================================================

    // DOM Utilities
    getConversationDiv() {
        const conversationDiv = document.getElementById('conversation');
        if (!conversationDiv) {
            console.error('❌ ERROR: Conversation element not found!');
        }
        return conversationDiv;
    }

    createElement(tag, className = '', id = '', innerHTML = '') {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (id) element.id = id;
        if (innerHTML) element.innerHTML = innerHTML;
        return element;
    }

    appendToConversation(element) {
        const conversationDiv = this.getConversationDiv();
        if (conversationDiv && element) {
            conversationDiv.appendChild(element);
            conversationDiv.scrollTop = conversationDiv.scrollHeight;
        }
    }

    clearConversation() {
        const conversationDiv = this.getConversationDiv();
        if (conversationDiv) {
            conversationDiv.innerHTML = '';
        }
    }

    showConversationMessage(message, className = 'loading') {
        const messageDiv = this.createElement('div', className, '', message);
        this.clearConversation();
        this.appendToConversation(messageDiv);
    }

    // Team Member Creation Utilities
    createMemberDiv(memberId, className) {
        const memberDiv = this.createElement('div', `team-member ${className}`, memberId);
        return memberDiv;
    }

    appendToTeamMembers(memberDiv, insertAfterModerator = false) {
        const teamMembersDiv = document.getElementById('teamMembers');
        if (teamMembersDiv && memberDiv) {
            if (insertAfterModerator) {
                const moderator = teamMembersDiv.querySelector('.moderator');
                if (moderator) {
                    teamMembersDiv.insertBefore(memberDiv, moderator.nextSibling);
                    return;
                }
            }
            teamMembersDiv.appendChild(memberDiv);
        }
    }

    // Model Selection Utilities
    getModelInfo(modelValue) {
        return this.modelOptions.find(m => m.value === modelValue) || this.modelOptions[0];
    }

    // ============================================================================
    
    async initializeLogging() {
        try {
            // Load config from server
            const response = await fetch('/config.js');
            const configText = await response.text();
            eval(configText); // This sets window.APP_CONFIG
            
            this.logLevel = window.APP_CONFIG?.frontend?.log_level || 'info';
            this.logFile = window.APP_CONFIG?.frontend?.log_file || 'logs/frontend.log';
            
            this.logs = [];
            this.log('info', 'Frontend logging initialized');
            
            // Start periodic log writing
            setInterval(() => this.writeLogs(), 5000);
        } catch (e) {
            console.warn('Could not initialize logging:', e);
            this.logLevel = 'info';
        }
    }
    
    log(level, message, data = null) {
        const logLevels = { error: 0, warn: 1, info: 2, debug: 3 };
        const currentLevel = logLevels[this.logLevel] || 2;
        const messageLevel = logLevels[level] || 2;
        
        if (messageLevel <= currentLevel) {
            const logEntry = {
                timestamp: new Date().toISOString(),
                level: level.toUpperCase(),
                message: message,
                data: data
            };
            
            this.logs.push(logEntry);
            console.log(`[${logEntry.timestamp}] ${logEntry.level}: ${message}`, data || '');
            
            // Keep only last 1000 log entries in memory
            if (this.logs.length > 1000) {
                this.logs = this.logs.slice(-1000);
            }
        }
    }
    
    async writeLogs() {
        if (this.logs.length === 0) return;
        
        try {
            const logData = this.logs.map(log => 
                `${log.timestamp} - ${log.level} - ${log.message}${log.data ? ' - ' + JSON.stringify(log.data) : ''}`
            ).join('\n') + '\n';
            
            // Send logs to backend for writing
            await fetch(`${this.apiUrl}/logs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    source: 'frontend',
                    logs: logData 
                })
            }).catch(() => {
                // Silently fail if backend is not available
            });
            
            this.logs = []; // Clear logs after writing
        } catch (error) {
            // Silently fail log writing - error intentionally unused
            console.error('Log writing failed:', error);
        }
    }
    
    initializeEventListeners() {
        // File upload
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');
        
        fileInput.addEventListener('change', this.handleFileSelect.bind(this));
        
        // Drag and drop
        uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
        uploadArea.addEventListener('dragleave', this.handleDragLeave.bind(this));
        uploadArea.addEventListener('drop', this.handleFileDrop.bind(this));
        
        // Team template selection
        const teamTemplateSelect = document.getElementById('teamTemplateSelect');
        if (teamTemplateSelect) {
            teamTemplateSelect.addEventListener('change', this.loadTeamTemplate.bind(this));
        }
        
        // Team name card click - set up event listener instead of inline onclick
        const teamNameCard = document.getElementById('teamNameCard');
        if (teamNameCard) {
            const teamNameHeader = teamNameCard.querySelector('.member-header');
            if (teamNameHeader) {
                teamNameHeader.addEventListener('click', () => {
                    console.log('Team name card clicked!');
                    this.toggleMemberCard('teamNameCard');
                });
                // Make sure it looks clickable
                teamNameHeader.style.cursor = 'pointer';
            }
        }
        
        // Team name input change
        const teamNameInput = document.getElementById('teamNameInput');
        if (teamNameInput) {
            teamNameInput.addEventListener('change', () => {
                this.updateTeamNameDisplay();
            });
            teamNameInput.addEventListener('input', () => {
                this.updateTeamNameDisplay();
            });
        }
        
        // Add team member button
        const addMemberBtn = document.querySelector('.add-member-btn');
        if (addMemberBtn) {
            addMemberBtn.addEventListener('click', () => {
                console.log('Add team member clicked!');
                this.addTeamMember();
            });
        }
        
        // Add customer button
        const addCustomerBtn = document.getElementById('addCustomerBtn');
        if (addCustomerBtn) {
            addCustomerBtn.addEventListener('click', () => {
                console.log('Add customer clicked!');
                this.addCustomerMember();
            });
        }
        
        // Save team configuration button
        const saveTeamBtn = document.getElementById('saveTeamBtn');
        if (saveTeamBtn) {
            saveTeamBtn.addEventListener('click', () => {
                console.log('Save team configuration clicked!');
                this.saveTeamConfiguration();
            });
        }
        
        // Upload button
        const uploadBtn = document.getElementById('uploadBtn');
        if (uploadBtn) {
            uploadBtn.addEventListener('click', () => {
                console.log('Upload button clicked!');
                document.getElementById('fileInput').click();
            });
        }
        
        // Load team configuration button
        const loadTeamBtn = document.getElementById('loadTeamBtn');
        if (loadTeamBtn) {
            loadTeamBtn.addEventListener('click', () => {
                console.log('Load team configuration clicked!');
                document.getElementById('teamConfigFileInput').click();
            });
        }
        
        // Team configuration file input
        const teamConfigFileInput = document.getElementById('teamConfigFileInput');
        if (teamConfigFileInput) {
            teamConfigFileInput.addEventListener('change', (event) => {
                console.log('Team config file selected!');
                this.loadTeamConfiguration(event);
            });
        }
        
        // Start discussion button
        const startBtn = document.getElementById('startBtn');
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                console.log('Start discussion clicked!');
                this.startDiscussion();
            });
        }
        
        // Revert button
        const revertBtn = document.getElementById('revertBtn');
        if (revertBtn) {
            revertBtn.addEventListener('click', () => {
                console.log('Revert clicked!');
                this.revertToPreviousMessage();
            });
        }
        
        // Regenerate button
        const regenerateBtn = document.getElementById('regenerateBtn');
        if (regenerateBtn) {
            regenerateBtn.addEventListener('click', () => {
                console.log('Regenerate clicked!');
                this.regenerateLastResponses();
            });
        }
        
        // Send button
        const sendBtn = document.getElementById('sendBtn');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                console.log('Send clicked!');
                this.sendPrompt();
            });
        }
        
        // Export markdown button
        const exportMarkdownBtn = document.getElementById('exportMarkdownBtn');
        if (exportMarkdownBtn) {
            exportMarkdownBtn.addEventListener('click', () => {
                console.log('Export markdown clicked!');
                this.exportConversation('markdown');
            });
        }
        
        // Export PDF button
        const exportPdfBtn = document.getElementById('exportPdfBtn');
        if (exportPdfBtn) {
            exportPdfBtn.addEventListener('click', () => {
                console.log('Export PDF clicked!');
                this.exportConversation('pdf');
            });
        }
        
        // Generate action plan button
        const summaryBtn = document.getElementById('summaryBtn');
        if (summaryBtn) {
            summaryBtn.addEventListener('click', () => {
                console.log('Generate action plan clicked!');
                this.generateActionPlan();
            });
        }
        
        // Download action plan buttons
        const downloadMarkdownBtn = document.getElementById('downloadMarkdownBtn');
        if (downloadMarkdownBtn) {
            downloadMarkdownBtn.addEventListener('click', () => {
                console.log('Download action plan as Markdown clicked!');
                this.downloadActionPlan('markdown');
            });
        }
        
        const downloadPdfBtn = document.getElementById('downloadPdfBtn');
        if (downloadPdfBtn) {
            downloadPdfBtn.addEventListener('click', () => {
                console.log('Download action plan as PDF clicked!');
                this.downloadActionPlan('pdf');
            });
        }
        
        // Close action plan button
        const closeActionPlanBtn = document.getElementById('closeActionPlanBtn');
        if (closeActionPlanBtn) {
            closeActionPlanBtn.addEventListener('click', () => {
                console.log('Close action plan clicked!');
                this.closeActionPlan();
            });
        }
        
        // Enter key in prompt input
        document.getElementById('promptInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendPrompt();
            }
        });
    }
    
    handleDragOver(e) {
        e.preventDefault();
        document.getElementById('uploadArea').classList.add('dragover');
    }
    
    handleDragLeave(e) {
        e.preventDefault();
        document.getElementById('uploadArea').classList.remove('dragover');
    }
    
    handleFileDrop(e) {
        e.preventDefault();
        document.getElementById('uploadArea').classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            this.uploadFiles(files);
        }
    }
    
    handleFileSelect(e) {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            this.uploadFiles(files);
        }
    }
    
    async uploadFiles(files) {
        // Check total document limit
        if (this.documents.length + files.length > this.maxDocuments) {
            this.showStatus(`Cannot upload more than ${this.maxDocuments} documents total`, 'error');
            return;
        }
        
        this.log('info', 'Starting multiple file upload', { count: files.length, filenames: files.map(f => f.name) });
        this.showStatus(`Uploading ${files.length} document(s)...`, 'loading');
        
        let successCount = 0;
        let failCount = 0;
        
        for (const file of files) {
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch(`${this.apiUrl}/upload`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`Upload failed: ${response.statusText}`);
                }
                
                const result = await response.json();
                
                // Add to documents array
                this.documents.push({
                    id: result.document_id,
                    filename: result.filename,
                    size: file.size
                });
                
                this.log('info', 'File uploaded successfully', { documentId: result.document_id, filename: result.filename });
                successCount++;
                
            } catch (error) {
                this.log('error', 'Upload error', { filename: file.name, error: error.message });
                failCount++;
            }
        }
        
        // Update UI
        this.updateDocumentsList();
        this.updateStartButton();
        
        // Show status
        if (failCount === 0) {
            this.showStatus(`Successfully uploaded ${successCount} document(s)`, 'success');
        } else if (successCount === 0) {
            this.showStatus(`Failed to upload all ${failCount} document(s)`, 'error');
        } else {
            this.showStatus(`Uploaded ${successCount} document(s), ${failCount} failed`, 'success');
        }
        
        // Clear file input
        document.getElementById('fileInput').value = '';
    }
    
    updateDocumentsList() {
        const documentsSection = document.getElementById('uploadedDocuments');
        const documentsList = document.getElementById('documentsList');
        
        if (this.documents.length === 0) {
            documentsSection.style.display = 'none';
            return;
        }
        
        documentsSection.style.display = 'block';
        documentsList.innerHTML = '';
        
        this.documents.forEach((doc, index) => {
            const docItem = document.createElement('div');
            docItem.className = 'document-item';
            docItem.innerHTML = `
                <div class="document-name">${doc.filename}</div>
                <div class="document-size">${this.formatFileSize(doc.size)}</div>
                <button class="remove-doc" data-index="${index}">×</button>
            `;
            
            // Add event listener to the remove button
            const removeBtn = docItem.querySelector('.remove-doc');
            removeBtn.addEventListener('click', () => {
                console.log(`Remove document ${index} clicked!`);
                this.removeDocument(index);
            });
            
            documentsList.appendChild(docItem);
        });
    }
    
    removeDocument(index) {
        this.documents.splice(index, 1);
        this.updateDocumentsList();
        this.updateStartButton();
        this.log('info', 'Document removed', { index });
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
    
    addTeamMember() {
        this.memberCounter++;
        const memberId = `member_${this.memberCounter}`;
        
        const memberDiv = document.createElement('div');
        memberDiv.className = 'team-member';
        memberDiv.id = memberId;
        
        memberDiv.innerHTML = `
            <div class="member-header">
                <div class="member-summary">
                    <span class="member-avatar">👤</span>
                    <div class="member-info">
                        <span class="member-display-name">New Team Member</span>
                        <span class="member-display-role">Click to configure</span>
                    </div>
                </div>
                <div class="expand-icon">▼</div>
            </div>
            <div class="member-details collapsed">
                <div class="member-field">
                    <label class="field-label">👤 Name</label>
                    <input type="text" placeholder="e.g., Alice, Product Manager" class="member-name" 
                           title="Display name for this team member">
                </div>
                <div class="member-field">
                    <label class="field-label">💼 Role</label>
                    <input type="text" placeholder="e.g., Product Manager, Engineer" class="member-role"
                           title="Professional role that defines expertise and review perspective">
                </div>
                <div class="member-field">
                    <label class="field-label">🧠 Model</label>
                    <select class="member-model"
                            title="AI model to use - higher = better quality, slower">
                        ${this.generateModelOptionsHtml()}
                    </select>
                </div>
                <button class="btn remove-member-btn">
                    Remove
                </button>
            </div>
        `;
        
        document.getElementById('teamMembers').appendChild(memberDiv);
        
        // Set up event listeners for the new member
        this.setupMemberEventListeners(memberId);
        
        this.updateStartButton();
        this.updateTeamIndicators();
    }
    
    addCustomerMember() {
        this.memberCounter++;
        const memberId = `customer_${this.memberCounter}`;
        
        const memberDiv = document.createElement('div');
        memberDiv.className = 'team-member customer-member';
        memberDiv.id = memberId;
        
        // Pre-filled customer values
        const customerNames = [
            'Customer Representative',
            'End User',
            'Product User',
            'Client Representative',
            'Customer Advocate'
        ];
        const customerName = customerNames[Math.floor(Math.random() * customerNames.length)];
        
        memberDiv.innerHTML = `
            <div class="member-header">
                <div class="member-summary">
                    <span class="member-avatar">🛒</span>
                    <div class="member-info">
                        <span class="member-display-name">${customerName}</span>
                        <span class="member-display-role">Customer Perspective & User Experience</span>
                    </div>
                    <span class="customer-badge" title="Customer representative providing user perspective" style="background: #FF9900; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">Customer</span>
                </div>
                <div class="expand-icon">▼</div>
            </div>
            <div class="member-details collapsed">
                <div class="member-field">
                    <label class="field-label">👤 Name</label>
                    <input type="text" value="${customerName}" class="member-name" 
                           title="Display name for this customer representative">
                </div>
                <div class="member-field">
                    <label class="field-label">💼 Role</label>
                    <input type="text" value="Customer Perspective & User Experience" class="member-role"
                           title="Role focused on user needs, pain points, and experience">
                </div>
                <div class="member-field">
                    <label class="field-label">🧠 Model</label>
                    <select class="member-model"
                            title="AI model to use - higher = better quality, slower">
                        ${this.generateModelOptionsHtml()}
                    </select>
                </div>
                <div class="customer-info" style="background: #fff3cd; padding: 8px; border-radius: 6px; font-size: 12px; color: #856404; margin-top: 8px;">
                    🛒 This agent provides customer perspective, focusing on usability, user experience, and real-world usage scenarios
                </div>
                <button class="btn remove-member-btn">
                    Remove
                </button>
            </div>
        `;
        
        // Insert after the Team Moderator but before other members
        const teamMembersDiv = document.getElementById('teamMembers');
        const moderator = teamMembersDiv.querySelector('.synthesizer-agent');
        if (moderator && moderator.nextSibling) {
            teamMembersDiv.insertBefore(memberDiv, moderator.nextSibling);
        } else {
            teamMembersDiv.appendChild(memberDiv);
        }
        
        // Set up event listeners for the new member
        this.setupMemberEventListeners(memberId);
        
        // Update the display immediately
        this.updateMemberDisplay(memberId);
        
        this.updateStartButton();
        this.updateTeamIndicators();
        
        this.log('info', 'Customer member added', { memberId, name: customerName });
    }
    
    setupMemberEventListeners(memberId) {
        const memberDiv = document.getElementById(memberId);
        if (!memberDiv) return;
        
        // Header click to toggle expansion
        const header = memberDiv.querySelector('.member-header');
        if (header) {
            header.addEventListener('click', () => {
                this.toggleMemberCard(memberId);
            });
            header.style.cursor = 'pointer';
        }
        
        // Name input change
        const nameInput = memberDiv.querySelector('.member-name');
        if (nameInput && !nameInput.readOnly) {
            nameInput.addEventListener('change', () => {
                this.updateMemberDisplay(memberId);
            });
            nameInput.addEventListener('input', () => {
                this.updateMemberDisplay(memberId);
            });
        }
        
        // Role input change  
        const roleInput = memberDiv.querySelector('.member-role');
        if (roleInput && !roleInput.readOnly) {
            roleInput.addEventListener('change', () => {
                this.updateMemberDisplay(memberId);
            });
            roleInput.addEventListener('input', () => {
                this.updateMemberDisplay(memberId);
            });
        }
        
        // Model select change
        const modelSelect = memberDiv.querySelector('.member-model');
        if (modelSelect) {
            modelSelect.addEventListener('change', () => {
                this.updateStartButton();
            });
        }
        
        // Remove button click
        const removeBtn = memberDiv.querySelector('.remove-member-btn');
        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                this.removeTeamMember(memberId);
            });
        }
    }
    
    addSynthesizerAgent() {
        // Add the Team Moderator as the first team member (locked name/role)
        this.memberCounter++;
        const memberId = `synthesizer_${this.memberCounter}`;
        
        const memberDiv = document.createElement('div');
        memberDiv.className = 'team-member synthesizer-agent';
        memberDiv.id = memberId;
        
        memberDiv.innerHTML = `
            <div class="member-header">
                <div class="member-summary">
                    <span class="member-avatar">⚖️</span>
                    <div class="member-info">
                        <span class="member-display-name">Team Moderator</span>
                        <span class="member-display-role">Discussion Analysis & Synthesis</span>
                    </div>
                    <span class="synthesizer-badge" title="Special agent that moderates and synthesizes team feedback">⭐</span>
                </div>
                <div class="expand-icon">▼</div>
            </div>
            <div class="member-details collapsed">
                <div class="member-field">
                    <label class="field-label">👤 Name</label>
                    <input type="text" value="Team Moderator" class="member-name" readonly
                           title="Fixed name - this agent specializes in moderating team discussions">
                </div>
                <div class="member-field">
                    <label class="field-label">💼 Role</label>
                    <input type="text" value="Discussion Analysis & Synthesis" class="member-role" readonly
                           title="Fixed role - analyzes conflicts, synergies, and provides actionable synthesis">
                </div>
                <div class="member-field">
                    <label class="field-label">🧠 Model</label>
                    <select class="member-model"
                            title="AI model to use - higher = better quality, slower">
                        ${this.generateModelOptionsHtml()}
                    </select>
                </div>
                <div class="synthesizer-info" style="background: #f8f9fa; padding: 8px; border-radius: 6px; font-size: 12px; color: #495057; margin-top: 8px;">
                    🔍 This agent analyzes all team feedback to identify conflicts, find synergies, and provide actionable synthesis
                </div>
            </div>
        `;
        
        document.getElementById('teamMembers').appendChild(memberDiv);
        
        // Set up event listeners for the synthesizer agent
        this.setupMemberEventListeners(memberId);
        
        this.updateStartButton();
        this.updateTeamIndicators();
    }

    addDefaultTeamMembers() {
        // First add the Discussion Synthesizer
        this.addSynthesizerAgent();
        
        // Then add regular team members
        const defaultMembers = [
            { name: 'Product Manager', role: 'Product Strategy and Market Analysis' },
            { name: 'Tech Lead', role: 'Technical Architecture and Implementation' },
            { name: 'UX Designer', role: 'User Experience and Interface Design' },
            { name: 'QA Engineer', role: 'Quality Assurance and Testing' }
        ];
        
        defaultMembers.forEach(member => {
            this.addTeamMember();
            const lastMember = document.querySelector('.team-member:last-child');
            const nameInput = lastMember.querySelector('.member-name');
            const roleInput = lastMember.querySelector('.member-role');
            
            nameInput.value = member.name;
            roleInput.value = member.role;
            
            // Update the display immediately
            this.updateMemberDisplay(lastMember.id);
        });
        
        this.updateStartButton();
    }
    
    toggleMemberCard(memberId) {
        console.log('Toggling member card:', memberId);
        const memberDiv = document.getElementById(memberId);
        
        if (!memberDiv) {
            console.error('Member div not found:', memberId);
            return;
        }
        
        const details = memberDiv.querySelector('.member-details');
        const expandIcon = memberDiv.querySelector('.expand-icon');
        
        if (!details) {
            console.error('Member details not found for:', memberId);
            return;
        }
        
        if (details.classList.contains('collapsed')) {
            details.classList.remove('collapsed');
            expandIcon.textContent = '▲';
            console.log('Expanded card:', memberId);
        } else {
            details.classList.add('collapsed');
            expandIcon.textContent = '▼';
            console.log('Collapsed card:', memberId);
        }
    }
    
    saveTeamConfiguration() {
        const teamNameInput = document.getElementById('teamNameInput');
        const teamName = teamNameInput.value.trim() || 'Default Review Team';
        
        // Get current team configuration
        const teamMembers = this.getTeamMembers();
        
        // Create configuration object
        const config = {
            teamName: teamName,
            createdAt: new Date().toISOString(),
            version: "1.0",
            moderator: {
                model: teamMembers.find(m => m.name === 'Team Moderator')?.model || 'nova-pro'
            },
            members: teamMembers
                .filter(m => m.name !== 'Team Moderator')
                .map(member => ({
                    name: member.name,
                    role: member.role,
                    model: member.model
                }))
        };
        
        // Create filename (lowercase with dashes)
        const filename = teamName.toLowerCase()
            .replace(/[^a-z0-9\s]/g, '') // Remove special chars
            .replace(/\s+/g, '-') // Replace spaces with dashes
            .replace(/-+/g, '-') // Replace multiple dashes with single
            .replace(/^-|-$/g, '') // Remove leading/trailing dashes
            + '.json';
        
        // Create and download file
        const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showStatus(`Team configuration saved as ${filename}`, 'success');
        this.log('info', 'Team configuration saved', { teamName, filename, memberCount: config.members.length });
    }
    
    loadTeamConfiguration(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const config = JSON.parse(e.target.result);
                
                // Validate configuration structure
                if (!config.teamName || !config.members || !Array.isArray(config.members)) {
                    throw new Error('Invalid team configuration format');
                }
                
                // Use shared loading logic
                this.loadTeamConfigurationFromObject(config);
                this.showStatus(`Team configuration "${config.teamName}" loaded successfully`, 'success');
                this.log('info', 'Team configuration loaded', { 
                    teamName: config.teamName, 
                    memberCount: config.members.length,
                    moderatorModel: config.moderator?.model 
                });
                
            } catch (error) {
                this.showStatus(`Failed to load team configuration: ${error.message}`, 'error');
                this.log('error', 'Failed to load team configuration', { error: error.message });
            }
        };
        
        reader.readAsText(file);
        
        // Clear the file input so the same file can be loaded again
        event.target.value = '';
    }
    
    updateTeamNameDisplay() {
        const teamNameInput = document.getElementById('teamNameInput');
        const teamNameDisplay = document.getElementById('teamNameDisplay');
        const teamName = teamNameInput.value.trim() || 'Default Review Team';
        teamNameDisplay.textContent = teamName;
        this.updateTeamIndicators();
    }
    
    getTeamTemplates() {
        return {
            'quick-review': {
                teamName: "Quick Review Team",
                moderator: { model: "nova-lite" },
                members: [
                    { name: "Product Manager", role: "Product Strategy & Requirements", model: "nova-lite" },
                    { name: "Tech Lead", role: "Technical Architecture & Implementation", model: "nova-pro" }
                ]
            },
            'full-stack': {
                teamName: "Full Stack Review Team", 
                moderator: { model: "nova-pro" },
                members: [
                    { name: "Frontend Developer", role: "User Interface & Client-Side Logic", model: "nova-lite" },
                    { name: "Backend Developer", role: "Server Architecture & APIs", model: "nova-pro" },
                    { name: "DevOps Engineer", role: "Infrastructure & Deployment", model: "nova-lite" },
                    { name: "QA Engineer", role: "Quality Assurance & Testing", model: "nova-lite" }
                ]
            },
            'security-audit': {
                teamName: "Security Audit Team",
                moderator: { model: "nova-premier" },
                members: [
                    { name: "Security Lead", role: "Security Architecture & Threat Analysis", model: "nova-premier" },
                    { name: "Compliance Officer", role: "Regulatory Compliance & Standards", model: "nova-pro" },
                    { name: "Risk Analyst", role: "Risk Assessment & Mitigation", model: "nova-pro" }
                ]
            },
            'design-review': {
                teamName: "Design Review Team",
                moderator: { model: "nova-pro" },
                members: [
                    { name: "UX Designer", role: "User Experience & Interaction Design", model: "nova-pro" },
                    { name: "UI Designer", role: "Visual Design & Interface", model: "nova-lite" },
                    { name: "Product Manager", role: "Product Strategy & User Needs", model: "nova-lite" },
                    { name: "Frontend Developer", role: "Technical Feasibility & Implementation", model: "nova-lite" }
                ]
            },
            'content-review': {
                teamName: "Content Review Team",
                moderator: { model: "nova-pro" },
                members: [
                    { name: "Content Strategist", role: "Content Strategy & Planning", model: "nova-pro" },
                    { name: "Technical Writer", role: "Documentation & Technical Communication", model: "nova-lite" },
                    { name: "Marketing Lead", role: "Brand Voice & Messaging", model: "nova-lite" },
                    { name: "Subject Matter Expert", role: "Domain Knowledge & Accuracy", model: "nova-lite" }
                ]
            },
            'business-review': {
                teamName: "Business Review Team",
                moderator: { model: "nova-pro" },
                members: [
                    { name: "Business Analyst", role: "Business Strategy & Process Analysis", model: "nova-pro" },
                    { name: "Financial Analyst", role: "Financial Planning & Risk Assessment", model: "nova-lite" },
                    { name: "Operations Manager", role: "Operational Efficiency & Implementation", model: "nova-lite" }
                ]
            },
            'api-review': {
                teamName: "API Review Team",
                moderator: { model: "nova-pro" },
                members: [
                    { name: "Backend Developer", role: "API Implementation & Architecture", model: "nova-pro" },
                    { name: "API Architect", role: "API Design & Standards", model: "nova-pro" },
                    { name: "QA Engineer", role: "API Testing & Validation", model: "nova-lite" }
                ]
            }
        };
    }
    
    loadTeamTemplate() {
        try {
            const templateSelect = document.getElementById('teamTemplateSelect');
            if (!templateSelect) {
                console.error('Template select element not found');
                return;
            }
            
            const templateId = templateSelect.value;
            console.log('Loading template:', templateId);
            
            if (!templateId) {
                console.log('No template ID selected');
                return;
            }
            
            // Handle empty template special case
            if (templateId === 'empty') {
                const emptyConfig = {
                    teamName: "New Team",
                    moderator: { model: "nova-lite" },
                    members: [],
                    createdAt: new Date().toISOString(),
                    version: "1.0"
                };
                
                setTimeout(() => {
                    this.loadTeamConfigurationFromObject(emptyConfig);
                    templateSelect.value = '';
                    this.showStatus(`✅ Created empty team (0 members)`, 'success');
                    this.log('info', 'Empty team created');
                    console.log('Empty team created successfully');
                }, 300);
                return;
            }
            
            const templates = this.getTeamTemplates();
            const template = templates[templateId];
            
            if (!template) {
                console.error('Template not found:', templateId);
                this.showStatus('Template not found', 'error');
                return;
            }
            
            console.log('Template found:', template);
            
            // Show brief loading feedback
            this.showStatus(`Loading ${template.teamName}...`, 'loading');
            
            // Load the template as if it was a saved configuration
            const config = {
                teamName: template.teamName,
                moderator: template.moderator,
                members: template.members,
                createdAt: new Date().toISOString(),
                version: "1.0"
            };
            
            // Simulate loading from file with brief delay for user feedback
            setTimeout(() => {
                this.loadTeamConfigurationFromObject(config);
                
                // Reset the dropdown
                templateSelect.value = '';
                
                this.showStatus(`✅ Loaded template: ${template.teamName} (${config.members.length} members)`, 'success');
                this.log('info', 'Template loaded', { templateId, teamName: template.teamName });
                
                console.log('Template loaded successfully:', template.teamName);
            }, 300);
        } catch (error) {
            console.error('Error loading template:', error);
            this.showStatus('Error loading template', 'error');
        }
    }
    
    loadTeamConfigurationFromObject(config) {
        // Update team name
        const teamNameInput = document.getElementById('teamNameInput');
        teamNameInput.value = config.teamName;
        this.updateTeamNameDisplay();
        
        // Clear existing team members
        const teamMembersDiv = document.getElementById('teamMembers');
        teamMembersDiv.innerHTML = '';
        this.memberCounter = 0;
        
        // Add Team Moderator first
        this.addSynthesizerAgent();
        
        // Set moderator model if specified
        if (config.moderator && config.moderator.model) {
            const moderatorCard = document.querySelector('.synthesizer-agent');
            if (moderatorCard) {
                const modelSelect = moderatorCard.querySelector('.member-model');
                if (modelSelect) {
                    modelSelect.value = config.moderator.model;
                }
            }
        }
        
        // Add regular team members
        config.members.forEach((memberConfig, index) => {
            this.addTeamMember();
            const lastMember = document.querySelector('.team-member:last-child');
            const nameInput = lastMember.querySelector('.member-name');
            const roleInput = lastMember.querySelector('.member-role');
            const modelSelect = lastMember.querySelector('.member-model');
            
            nameInput.value = memberConfig.name || '';
            roleInput.value = memberConfig.role || '';
            modelSelect.value = memberConfig.model || 'nova-lite';
            
            // Update display
            this.updateMemberDisplay(lastMember.id);
        });
        
        this.updateStartButton();
        this.updateTeamIndicators();
        
        // Add a subtle visual cue that the team was updated
        const teamNameDisplay = document.getElementById('teamNameDisplay');
        if (teamNameDisplay) {
            teamNameDisplay.style.transition = 'background-color 0.5s ease';
            teamNameDisplay.style.backgroundColor = '#d4edda';
            setTimeout(() => {
                teamNameDisplay.style.backgroundColor = '';
            }, 1500);
        }
    }
    
    updateTeamIndicators() {
        const teamMembers = this.getTeamMembers();
        const nonModeratorMembers = teamMembers.filter(m => m.name !== 'Team Moderator');
        
        // Count models
        const modelCounts = {};
        teamMembers.forEach(member => {
            modelCounts[member.model] = (modelCounts[member.model] || 0) + 1;
        });
        
        // Update team stats display
        const teamStatsDisplay = document.getElementById('teamStatsDisplay');
        teamStatsDisplay.textContent = `👥 ${nonModeratorMembers.length} members`;
        
        // Update visual indicators
        const teamIndicators = document.getElementById('teamIndicators');
        if (!teamIndicators) return;
        
        teamIndicators.innerHTML = '';
        
        // Member count badge
        const memberBadge = document.createElement('span');
        memberBadge.style.cssText = 'background: #007bff; color: white; font-size: 10px; padding: 2px 6px; border-radius: 8px; font-weight: 600;';
        memberBadge.textContent = `${nonModeratorMembers.length}`;
        memberBadge.title = `${nonModeratorMembers.length} team members`;
        teamIndicators.appendChild(memberBadge);
        
        // Model distribution indicators
        const modelIcons = {
            'nova-micro': { icon: '⚪', color: '#6c757d', name: 'Micro' },
            'nova-lite': { icon: '🔵', color: '#17a2b8', name: 'Lite' },
            'nova-pro': { icon: '🟠', color: '#fd7e14', name: 'Pro' },
            'nova-premier': { icon: '🟣', color: '#6f42c1', name: 'Premier' }
        };
        
        Object.entries(modelCounts).forEach(([model, count]) => {
            if (count > 0) {
                const modelBadge = document.createElement('span');
                const modelInfo = modelIcons[model] || { icon: '❓', color: '#6c757d', name: model };
                modelBadge.style.cssText = `background: ${modelInfo.color}; color: white; font-size: 10px; padding: 2px 4px; border-radius: 6px; font-weight: 600; display: flex; align-items: center; gap: 2px;`;
                modelBadge.innerHTML = `${modelInfo.icon}${count}`;
                modelBadge.title = `${count} ${modelInfo.name} model${count > 1 ? 's' : ''}`;
                teamIndicators.appendChild(modelBadge);
            }
        });
    }
    
    updateMemberDisplay(memberId) {
        const memberDiv = document.getElementById(memberId);
        const nameInput = memberDiv.querySelector('.member-name');
        const roleInput = memberDiv.querySelector('.member-role');
        const displayName = memberDiv.querySelector('.member-display-name');
        const displayRole = memberDiv.querySelector('.member-display-role');
        
        // Update the display with current values
        displayName.textContent = nameInput.value || 'New Team Member';
        displayRole.textContent = roleInput.value || 'Click to configure';
        
        // Also update the start button
        this.updateStartButton();
        this.updateTeamIndicators();
    }
    
    removeTeamMember(memberId) {
        const memberDiv = document.getElementById(memberId);
        if (memberDiv) {
            memberDiv.remove();
            this.updateStartButton();
            this.updateTeamIndicators();
        }
    }
    
    updateStartButton() {
        const hasDocuments = this.documents.length > 0;
        const teamMembers = this.getTeamMembers();
        const hasValidTeam = teamMembers.length > 0 && 
                           teamMembers.every(m => m.name.trim() && m.role.trim());
        
        const startBtn = document.getElementById('startBtn');
        startBtn.disabled = !(hasDocuments && hasValidTeam);
        
        // Update button text and functionality based on session state
        this.updateStartButtonState();
    }
    
    updateStartButtonState() {
        const startBtn = document.getElementById('startBtn');
        
        if (this.sessionId) {
            // Active session - show restart option
            this.setButtonHandler('startBtn', () => this.showRestartConfirmation(), 'Restart Discussion');
            startBtn.title = 'Start a new discussion with current team settings';
        } else {
            // No active session - show start option
            this.setButtonHandler('startBtn', () => this.startDiscussion(), 'Start Discussion');
            startBtn.title = 'Begin discussion with uploaded documents and team';
        }
    }
    
    getTeamMembers() {
        const members = [];
        const memberDivs = document.querySelectorAll('.team-member');
        
        memberDivs.forEach((div, index) => {
            const nameInput = div.querySelector('.member-name');
            const roleInput = div.querySelector('.member-role');
            const modelSelect = div.querySelector('.member-model');
            
            // Check if elements exist before accessing their values
            if (nameInput && roleInput && modelSelect) {
                const name = nameInput.value.trim();
                const role = roleInput.value.trim();
                const model = modelSelect.value;
                
                if (name && role) {
                    members.push({
                        id: `member_${index + 1}`,
                        name: name,
                        role: role,
                        model: model
                    });
                }
            }
        });
        
        return members;
    }
    
    async startDiscussion() {
        // Verify DOM structure before starting discussion
        console.log('🚀 Starting discussion - verifying DOM structure first...');
        this.verifyDOMStructure();
        // Show the input area for initial prompt
        this.showInputArea();
        
        // Change the input placeholder and add initial instructions
        const promptInput = document.getElementById('promptInput');
        promptInput.placeholder = 'Enter your initial discussion prompt (e.g., "Please review this document and provide your initial thoughts and feedback.")';
        promptInput.value = 'Please review this document and provide your initial thoughts and feedback.';
        
        // Change the send button to say "Start Discussion"
        this.setButtonHandler('sendBtn', () => this.sendInitialPrompt(), 'Start Discussion');
        
        // Update Enter key handler for initial prompt
        this.setEnterKeyHandler(() => this.sendInitialPrompt());
        
        // Focus on the input
        promptInput.focus();
        promptInput.select();
        
        return;
    }
    
    showRestartConfirmation() {
        if (confirm('This will start a new discussion and clear the current conversation. Are you sure?')) {
            this.restartDiscussion();
        }
    }
    
    async restartDiscussion() {
        this.log('info', 'Restarting discussion with current documents and new team settings');
        
        // Check if we have valid documents
        if (this.documents.length === 0) {
            alert('Please upload documents before starting a discussion.');
            return;
        }
        
        // Reset session state but keep documents
        this.disconnectWebSocket();
        this.sessionId = null;
        
        // Clear conversation using utility
        this.showConversationMessage('Enter your initial discussion prompt to begin...');
        
        // Reset to initial prompt interface
        this.resetToInitialPromptInterface();
        
        // Update start button state
        this.updateStartButtonState();
        
        // Start new discussion with current documents
        this.startDiscussion();
    }
    
    async sendInitialPrompt() {
        const promptInput = document.getElementById('promptInput');
        const initialPrompt = promptInput.value.trim();
        
        if (!initialPrompt) {
            alert('Please enter an initial prompt to start the discussion.');
            return;
        }

        // Check if documents are uploaded
        if (!this.documents || this.documents.length === 0) {
            alert('🚫 Cannot start discussion: No documents uploaded.\n\nPlease upload at least one document before starting a discussion.');
            return;
        }

        // Check if there are team members besides the moderator
        const teamMembers = this.getTeamMembers();
        const nonModeratorMembers = teamMembers.filter(member => member.name !== 'Team Moderator');
        
        if (nonModeratorMembers.length === 0) {
            alert('🚫 Cannot start discussion: Only the Team Moderator is configured.\n\nThe Team Moderator analyzes feedback from other team members. Please add at least one regular team member (Product Manager, Tech Lead, etc.) to have a meaningful discussion.');
            return;
        }
        
        // Reset the button and input for normal conversation
        this.setButtonHandler('sendBtn', () => this.sendPrompt(), 'Send');
        promptInput.placeholder = 'Enter your prompt or question for the team...';
        promptInput.value = '';
        
        // Reset Enter key handler back to normal sendPrompt
        this.setEnterKeyHandler(() => this.sendPrompt());
        
        // Add user message to conversation immediately  
        this.addMessageToConversation({
            type: 'user',
            content: initialPrompt,
            timestamp: new Date().toISOString()
        });
        
        // Show interactive agents thinking animation
        this.showAgentsThinking();
        
        try {
            // Send all document IDs to the backend
            const documentIds = this.documents.map(doc => doc.id);
            
            console.log('🚀 Starting session with:', {
                documentIds: documentIds,
                teamMembers: teamMembers,
                initialPrompt: initialPrompt,
                apiUrl: this.apiUrl
            });
            
            const response = await fetch(`${this.apiUrl}/sessions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    document_ids: documentIds,
                    team_members: teamMembers,
                    initial_prompt: initialPrompt
                })
            });
            
            console.log('📡 Session API response status:', response.status, response.statusText);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ Session API error response:', errorText);
                throw new Error(`Failed to start discussion: ${response.statusText} - ${errorText}`);
            }
            
            const result = await response.json();
            this.sessionId = result.session_id;
            
            // Connect to WebSocket for real-time updates
            this.connectWebSocket(this.sessionId);
            
            // Now send the initial prompt to trigger agent responses
            const promptResponse = await fetch(`${this.apiUrl}/sessions/${this.sessionId}/prompt`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt: initialPrompt
                })
            });
            
            if (!promptResponse.ok) {
                throw new Error(`Failed to send initial prompt: ${promptResponse.statusText}`);
            }
            
            const promptResult = await promptResponse.json();
            
            // Clear the agents thinking animation
            this.clearAllTypingIndicators();
            
            // Agent responses will be added via WebSocket, so we don't need to add them here
            this.showDocumentInfo();
            this.updateControlsVisibility();
            this.updateStartButtonState();
            
        } catch (error) {
            this.showStatus(`Failed to start discussion: ${error.message}`, 'error');
            this.clearAllTypingIndicators();
        }
    }
    
    async sendPrompt() {
        const promptInput = document.getElementById('promptInput');
        const prompt = promptInput.value.trim();
        
        if (!prompt || !this.sessionId) return;
        
        promptInput.value = '';
        document.getElementById('sendBtn').disabled = true;
        
        // Add user message to conversation immediately
        this.addMessageToConversation({
            type: 'user',
            content: prompt,
            timestamp: new Date().toISOString()
        });
        
        // Show interactive agents thinking animation
        this.showAgentsThinking();
        
        try {
            const response = await fetch(`${this.apiUrl}/sessions/${this.sessionId}/prompt`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt: prompt
                })
            });
            
            if (!response.ok) {
                throw new Error(`Failed to send prompt: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Clear thinking indicators - responses will come via WebSocket
            this.clearAllTypingIndicators();
            
            this.updateControlsVisibility();
            
        } catch (error) {
            this.clearAllTypingIndicators();
            this.showStatus(`Failed to send prompt: ${error.message}`, 'error');
        } finally {
            document.getElementById('sendBtn').disabled = false;
        }
    }
    
    async regenerateLastResponses() {
        if (!this.sessionId) {
            this.showStatus('No active session to regenerate responses for', 'error');
            return;
        }
        
        this.log('info', 'Regenerating last agent responses');
        
        // Immediately remove old agent responses from the screen
        this.removeLastAgentResponses();
        
        // Disable controls during regeneration
        this.setControlsDisabled(true);
        this.showAgentsThinking();
        
        try {
            const response = await fetch(`${this.apiUrl}/sessions/${this.sessionId}/regenerate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
            
            if (!response.ok) {
                throw new Error(`Failed to regenerate responses: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Clear thinking indicators - responses will come via WebSocket
            this.clearAllTypingIndicators();
            
            this.log('info', 'Successfully regenerated agent responses');
            
        } catch (error) {
            this.clearAllTypingIndicators();
            this.log('error', 'Failed to regenerate responses', { error: error.message });
            this.showStatus(`Failed to regenerate responses: ${error.message}`, 'error');
        } finally {
            this.setControlsDisabled(false);
            this.updateControlsVisibility();
        }
    }
    
    async revertToPreviousMessage() {
        if (!this.sessionId) {
            this.showStatus('No active session to revert', 'error');
            return;
        }
        
        this.log('info', 'Reverting to previous message');
        
        // Disable controls during revert
        this.setControlsDisabled(true);
        this.showConversationLoading('Reverting conversation...');
        
        try {
            const response = await fetch(`${this.apiUrl}/sessions/${this.sessionId}/revert`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
            
            if (!response.ok) {
                throw new Error(`Failed to revert conversation: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Check if we reverted back to initial state (empty conversation)
            if (result.conversation.length === 0) {
                // Reset session state and return to initial prompt interface
                this.disconnectWebSocket();
                this.sessionId = null;
                this.resetToInitialPromptInterface();
                this.updateStartButtonState();
                this.log('info', 'Reverted to initial state - reset session and showing initial prompt interface');
            } else {
                this.displayConversation(result.conversation);
                this.log('info', 'Successfully reverted conversation');
            }
            
        } catch (error) {
            this.log('error', 'Failed to revert conversation', { error: error.message });
            this.showStatus(`Failed to revert conversation: ${error.message}`, 'error');
        } finally {
            this.clearConversationLoading();
            this.setControlsDisabled(false);
            this.updateControlsVisibility();
        }
    }
    
    setControlsDisabled(disabled) {
        document.getElementById('regenerateBtn').disabled = disabled;
        document.getElementById('revertBtn').disabled = disabled;
        document.getElementById('sendBtn').disabled = disabled;
        document.getElementById('summaryBtn').disabled = disabled;
        document.getElementById('summaryModelSelect').disabled = disabled;
        document.getElementById('promptInput').disabled = disabled;
        document.getElementById('exportMarkdownBtn').disabled = disabled;
        document.getElementById('exportPdfBtn').disabled = disabled;
        
        // Also disable action plan download buttons if they exist
        const downloadMarkdownBtn = document.getElementById('downloadMarkdownBtn');
        const downloadPdfBtn = document.getElementById('downloadPdfBtn');
        if (downloadMarkdownBtn) downloadMarkdownBtn.disabled = disabled;
        if (downloadPdfBtn) downloadPdfBtn.disabled = disabled;
    }
    
    updateControlsVisibility() {
        const regenerateBtn = document.getElementById('regenerateBtn');
        const revertBtn = document.getElementById('revertBtn');
        const summaryBtn = document.getElementById('summaryBtn');
        const summaryModelSelect = document.getElementById('summaryModelSelect');
        const summaryBar = document.getElementById('summaryBar');
        const summarySeparator = document.getElementById('summarySeparator');
        const exportMarkdownBtn = document.getElementById('exportMarkdownBtn');
        const exportPdfBtn = document.getElementById('exportPdfBtn');
        
        if (!this.sessionId) {
            regenerateBtn.classList.add('hidden');
            revertBtn.classList.add('hidden');
            summaryBtn.classList.add('hidden');
            summaryModelSelect.classList.add('hidden');
            summaryBar.classList.add('hidden');
            summarySeparator.classList.add('hidden');
            exportMarkdownBtn.classList.add('hidden');
            exportPdfBtn.classList.add('hidden');
            return;
        }
        
        // Show controls after first discussion round (when there are agent responses)
        const conversationDiv = document.getElementById('conversation');
        const agentMessages = conversationDiv.querySelectorAll('.message.agent');
        
        if (agentMessages.length > 0) {
            regenerateBtn.classList.remove('hidden');
            revertBtn.classList.remove('hidden');
            summaryBtn.classList.remove('hidden');
            summaryModelSelect.classList.remove('hidden');
            summaryBar.classList.remove('hidden');
            summarySeparator.classList.remove('hidden');
            exportMarkdownBtn.classList.remove('hidden');
            exportPdfBtn.classList.remove('hidden');
        } else {
            regenerateBtn.classList.add('hidden');
            revertBtn.classList.add('hidden');
            summaryBtn.classList.add('hidden');
            summaryModelSelect.classList.add('hidden');
            summaryBar.classList.add('hidden');
            summarySeparator.classList.add('hidden');
            exportMarkdownBtn.classList.add('hidden');
            exportPdfBtn.classList.add('hidden');
        }
    }
    
    resetToInitialPromptInterface() {
        // Clear the conversation display using utility
        this.showConversationMessage('Enter your initial discussion prompt to begin...');
        
        // Reset to initial prompt interface
        const promptInput = document.getElementById('promptInput');
        promptInput.placeholder = 'Enter your initial discussion prompt (e.g., "Please review this document and provide your initial thoughts and feedback.")';
        promptInput.value = 'Please review this document and provide your initial thoughts and feedback.';
        
        // Change the send button to say "Start Discussion"
        this.setButtonHandler('sendBtn', () => this.sendInitialPrompt(), 'Start Discussion');
        
        // Update Enter key handler for initial prompt
        this.setEnterKeyHandler(() => this.sendInitialPrompt());
        
        // Hide controls and document info
        document.getElementById('regenerateBtn').classList.add('hidden');
        document.getElementById('revertBtn').classList.add('hidden');
        document.getElementById('summaryBtn').classList.add('hidden');
        document.getElementById('summaryModelSelect').classList.add('hidden');
        document.getElementById('summaryBar').classList.add('hidden');
        document.getElementById('summarySeparator').classList.add('hidden');
        document.getElementById('exportMarkdownBtn').classList.add('hidden');
        document.getElementById('exportPdfBtn').classList.add('hidden');
        
        // Hide action plan section
        document.getElementById('actionPlanSection').classList.add('hidden');
        this.actionPlanData = null;
        
        const existingDocInfo = document.getElementById('documentInfo');
        if (existingDocInfo) {
            existingDocInfo.remove();
        }
        
        // Focus on the input
        promptInput.focus();
        promptInput.select();
        
        this.log('info', 'Reset to initial prompt interface');
    }
    
    removeLastAgentResponses() {
        const conversationDiv = document.getElementById('conversation');
        const messages = conversationDiv.querySelectorAll('.message');
        
        // Find the last user message
        let lastUserIndex = -1;
        for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].classList.contains('user')) {
                lastUserIndex = i;
                break;
            }
        }
        
        // Remove all messages after the last user message (these are agent responses)
        if (lastUserIndex !== -1) {
            for (let i = messages.length - 1; i > lastUserIndex; i--) {
                messages[i].remove();
            }
        }
        
        this.log('info', 'Removed old agent responses from display');
    }
    
    async generateActionPlan() {
        if (!this.sessionId) {
            this.showStatus('No active session to generate action plan for', 'error');
            return;
        }
        
        this.log('info', 'Generating action plan');
        
        // Disable controls during generation
        this.setControlsDisabled(true);
        this.showConversationLoading('Generating action plan...');
        
        try {
            // Get selected model
            const selectedModel = document.getElementById('summaryModelSelect').value;
            
            const response = await fetch(`${this.apiUrl}/sessions/${this.sessionId}/actionable-summary`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model: selectedModel
                })
            });
            
            if (!response.ok) {
                throw new Error(`Failed to generate action plan: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Store the action plan data for download
            this.actionPlanData = {
                content: result.summary,
                filename: result.filename
            };
            
            // Display the action plan in the UI
            this.displayActionPlan(result.summary);
            this.log('info', 'Successfully generated action plan');
            this.showStatus('Action plan generated successfully!', 'success');
            
        } catch (error) {
            this.log('error', 'Failed to generate action plan', { error: error.message });
            this.showStatus(`Failed to generate action plan: ${error.message}`, 'error');
        } finally {
            this.clearConversationLoading();
            this.setControlsDisabled(false);
        }
    }
    
    displayActionPlan(markdownContent) {
        const actionPlanSection = document.getElementById('actionPlanSection');
        const actionPlanContent = document.getElementById('actionPlanContent');
        const downloadMarkdownBtn = document.getElementById('downloadMarkdownBtn');
        const downloadPdfBtn = document.getElementById('downloadPdfBtn');
        
        // Render the markdown content
        actionPlanContent.innerHTML = this.formatMessageContent(markdownContent);
        
        // Show the action plan section and download buttons
        actionPlanSection.classList.remove('hidden');
        if (downloadMarkdownBtn) downloadMarkdownBtn.classList.remove('hidden');
        if (downloadPdfBtn) downloadPdfBtn.classList.remove('hidden');
        
        // Scroll to the action plan
        actionPlanSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        this.log('info', 'Action plan displayed in UI');
    }
    
    async downloadActionPlan(format = 'markdown') {
        if (!this.actionPlanData) {
            this.showStatus('No action plan to download', 'error');
            return;
        }
        
        if (format === 'pdf') {
            // Use the new backend content export endpoint for PDF generation
            try {
                const response = await fetch(`${this.apiUrl}/export/content`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        content: this.actionPlanData.content,
                        format: 'pdf',
                        filename: this.actionPlanData.filename.replace('.md', '.pdf')
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`PDF export failed: ${response.statusText}`);
                }
                
                // Download the PDF blob
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = this.actionPlanData.filename.replace('.md', '.pdf');
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.log('info', 'Action plan downloaded as PDF', { filename: this.actionPlanData.filename });
                this.showStatus('Action plan downloaded as PDF successfully!', 'success');
            } catch (error) {
                this.log('error', 'Failed to download action plan as PDF', { error: error.message });
                this.showStatus(`Failed to download PDF: ${error.message}`, 'error');
            }
        } else {
            this.downloadMarkdownFile(this.actionPlanData.content, this.actionPlanData.filename);
            this.log('info', 'Action plan downloaded as Markdown', { filename: this.actionPlanData.filename });
            this.showStatus('Action plan downloaded as Markdown successfully!', 'success');
        }
    }
    
    closeActionPlan() {
        const actionPlanSection = document.getElementById('actionPlanSection');
        actionPlanSection.classList.add('hidden');
        this.log('info', 'Action plan closed');
    }
    
    async exportConversation(format) {
        if (!this.sessionId) {
            this.showStatus('No active session to export', 'error');
            return;
        }
        
        this.log('info', 'Exporting conversation', { format });
        
        try {
            // Disable export buttons during export
            document.getElementById('exportMarkdownBtn').disabled = true;
            document.getElementById('exportPdfBtn').disabled = true;
            
            const response = await fetch(`${this.apiUrl}/sessions/${this.sessionId}/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    format: format,
                    include_metadata: true
                })
            });
            
            if (!response.ok) {
                throw new Error(`Export failed: ${response.statusText}`);
            }
            
            // Get the filename from the response headers
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `conversation_export.${format}`;
            if (contentDisposition) {
                const match = contentDisposition.match(/filename="?([^"]+)"?/);
                if (match) {
                    filename = match[1];
                }
            }
            
            // Download the file
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            
            // Trigger the download
            document.body.appendChild(link);
            link.click();
            
            // Clean up
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            this.log('info', 'Conversation exported successfully', { format, filename });
            this.showStatus(`Conversation exported as ${format.toUpperCase()}!`, 'success');
            
        } catch (error) {
            this.log('error', 'Failed to export conversation', { format, error: error.message });
            this.showStatus(`Failed to export conversation: ${error.message}`, 'error');
        } finally {
            // Re-enable export buttons
            document.getElementById('exportMarkdownBtn').disabled = false;
            document.getElementById('exportPdfBtn').disabled = false;
        }
    }

    downloadMarkdownFile(content, filename) {
        // Create a blob with the markdown content
        const blob = new Blob([content], { type: 'text/markdown' });
        
        // Create a temporary download link
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        
        // Trigger the download
        document.body.appendChild(link);
        link.click();
        
        // Clean up
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.log('info', 'Downloaded markdown file', { filename });
    }
    
    displayConversation(conversation) {
        this.clearConversation();
        
        conversation.forEach(message => {
            this.addMessageToConversation(message);
        });
        
        // Update controls visibility after displaying conversation
        this.updateControlsVisibility();
    }
    
    addMessageToConversation(message, withTypingEffect = false) {
        const conversationDiv = this.getConversationDiv();
        if (!conversationDiv) return;
        
        // Debug: Verify we have the correct conversation element
        console.log('🔍 Adding message to conversation element:', {
            id: conversationDiv.id,
            className: conversationDiv.className,
            parentElement: conversationDiv.parentElement?.className || 'no parent',
            parentId: conversationDiv.parentElement?.id || 'no parent id'
        });

        const messageDiv = this.createElement('div', `message ${message.type}`);
        
        let header = '';
        let avatarText = '';
        if (message.type === 'user') {
            header = message.content; // Show the actual message text as header
            avatarText = 'U';
        } else if (message.type === 'agent') {
            header = `${message.agent_name}`;
            const roleText = message.role ? ` (${message.role})` : '';
            avatarText = message.agent_name.charAt(0).toUpperCase();
        } else {
            header = 'System';
            avatarText = 'S';
        }
        
        const timestamp = new Date(message.timestamp).toLocaleTimeString();
        
        // Create avatar and bubble structure
        if (message.type === 'system') {
            messageDiv.innerHTML = `
                <div class="message-bubble">
                    <div class="message-header">
                        <span>${header}</span>
                        <span class="message-meta">${timestamp}</span>
                    </div>
                    <div class="message-content">${this.formatMessageContent(message.content)}</div>
                </div>
            `;
        } else if (message.type === 'user') {
            // For user messages, show content in header and just the avatar
            messageDiv.innerHTML = `
                <div class="message-avatar">${avatarText}</div>
                <div class="message-bubble">
                    <div class="message-header">
                        <span>${this.formatMessageContent(header)}</span>
                        <span class="message-meta">${timestamp}</span>
                    </div>
                </div>
            `;
        } else {
            // For agent messages, show normal structure with separate content
            const roleInfo = message.type === 'agent' && message.role ? `<div style="font-size: 11px; opacity: 0.7; margin-bottom: 2px;">${message.role}</div>` : '';
            
            messageDiv.innerHTML = `
                <div class="message-avatar">${avatarText}</div>
                <div class="message-bubble">
                    <div class="message-header">
                        <span>${header}</span>
                        <span class="message-meta">${timestamp}</span>
                    </div>
                    ${roleInfo}
                    <div class="message-content">${this.formatMessageContent(message.content)}</div>
                </div>
            `;
        }
        
        // Add subtle entrance animation for agent messages
        if (withTypingEffect && message.type === 'agent') {
            messageDiv.style.opacity = '0';
            messageDiv.style.transform = 'translateY(10px)';
            messageDiv.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        }
        
        this.appendToConversation(messageDiv);
        
        // Trigger entrance animation
        if (withTypingEffect && message.type === 'agent') {
            setTimeout(() => {
                messageDiv.style.opacity = '1';
                messageDiv.style.transform = 'translateY(0)';
            }, 100);
        }
    }
    
    formatMessageContent(content) {
        // Use marked.js library for markdown parsing
        if (typeof marked !== 'undefined') {
            // Configure marked for better styling
            marked.setOptions({
                breaks: true,
                gfm: true
            });
            return marked.parse(content);
        } else {
            // Fallback to basic formatting if marked.js is not available
            return content.replace(/\n/g, '<br>');
        }
    }
    
    showConversationLoading(message) {
        const conversationDiv = this.getConversationDiv();
        if (!conversationDiv) return;
        
        console.log('🔍 Loading indicator targeting:', conversationDiv.parentElement?.className || 'no parent', conversationDiv.parentElement?.id || 'no parent id');
        const loadingDiv = this.createElement('div', 'loading', 'conversationLoading', message);
        this.appendToConversation(loadingDiv);
    }
    
    showAgentsThinking() {
        // Remove any existing loading indicators
        this.clearConversationLoading();
        this.clearAllTypingIndicators();
        
        // Create the overall agents thinking indicator
        const agentsThinkingDiv = this.createElement('div', 'agents-thinking', 'agentsThinking');
        
        const teamMembers = this.getTeamMembers();
        
        agentsThinkingDiv.innerHTML = `
            <div class="agents-thinking-text">Team members are analyzing the documents...</div>
            <div class="agents-progress">
                ${teamMembers.map((member, index) => `
                    <div class="agent-progress-dot" title="${member.name} - ${member.role}">
                        ${member.name.charAt(0).toUpperCase()}
                    </div>
                `).join('')}
            </div>
            <div style="font-size: 12px; color: #6c757d;">💭 Each agent is bringing their unique perspective</div>
        `;
        
        const conversationDiv = this.getConversationDiv();
        if (conversationDiv) {
            conversationDiv.appendChild(agentsThinkingDiv);
            conversationDiv.scrollTop = conversationDiv.scrollHeight;
        }
    }
    
    showAgentTyping(agentName) {
        const conversationDiv = document.getElementById('conversation');
        
        // Create typing indicator for specific agent
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.id = `typing-${agentName.replace(/\s+/g, '')}`;
        
        typingDiv.innerHTML = `
            <div class="message-avatar">${agentName.charAt(0).toUpperCase()}</div>
            <div class="typing-bubble">
                <div class="typing-text">${agentName} is thinking...</div>
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        conversationDiv.appendChild(typingDiv);
        conversationDiv.scrollTop = conversationDiv.scrollHeight;
        
        return typingDiv;
    }
    
    removeAgentTyping(agentName) {
        const typingId = `typing-${agentName.replace(/\s+/g, '')}`;
        const typingDiv = document.getElementById(typingId);
        if (typingDiv) {
            typingDiv.remove();
        }
    }
    
    clearAllTypingIndicators() {
        // Remove agents thinking indicator
        const agentsThinking = document.getElementById('agentsThinking');
        if (agentsThinking) {
            agentsThinking.remove();
        }
        
        // Remove all individual typing indicators
        const typingIndicators = document.querySelectorAll('.typing-indicator');
        typingIndicators.forEach(indicator => indicator.remove());
    }
    
    async simulateSequentialAgentResponses(responses) {
        // Clear the overall thinking indicator
        const agentsThinking = document.getElementById('agentsThinking');
        if (agentsThinking) {
            agentsThinking.remove();
        }
        
        // Process responses sequentially with typing animations
        for (let i = 0; i < responses.length; i++) {
            const response = responses[i];
            
            // Show typing indicator for this agent
            this.showAgentTyping(response.agent_name, response.role);
            
            // Simulate thinking time (1-3 seconds random)
            const thinkingTime = 1500 + Math.random() * 2000;
            await new Promise(resolve => setTimeout(resolve, thinkingTime));
            
            // Remove typing indicator
            this.removeAgentTyping(response.agent_name);
            
            // Add the actual message with a slight typing effect
            this.addMessageToConversation(response, true);
            
            // Short pause before next agent (if not last)
            if (i < responses.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 800));
            }
        }
    }
    
    clearConversationLoading() {
        const loadingDiv = document.getElementById('conversationLoading');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }
    
    showInputArea() {
        document.getElementById('inputArea').classList.remove('hidden');
    }
    
    showDocumentInfo() {
        if (this.documents.length > 0) {
            const conversationDiv = document.getElementById('conversation');
            const existingInfo = document.getElementById('documentInfo');
            
            if (!existingInfo) {
                const infoDiv = document.createElement('div');
                infoDiv.id = 'documentInfo';
                infoDiv.style.cssText = `
                    background: #e8f4fd;
                    border: 1px solid #bee5eb;
                    border-radius: 6px;
                    padding: 12px;
                    margin-bottom: 15px;
                    font-size: 14px;
                    color: #0c5460;
                `;
                
                let documentsHtml = '<div style="font-weight: 600; margin-bottom: 8px;">📄 Documents in Discussion:</div>';
                this.documents.forEach((doc, index) => {
                    documentsHtml += `
                        <div style="margin-left: 10px; margin-bottom: 4px;">
                            ${index + 1}. ${doc.filename} <span style="color: #666; font-size: 12px;">(${this.formatFileSize(doc.size)})</span>
                        </div>
                    `;
                });
                
                infoDiv.innerHTML = documentsHtml;
                conversationDiv.insertBefore(infoDiv, conversationDiv.firstChild);
            }
        }
    }
    
    showStatus(message, type) {
        const statusDiv = document.getElementById('uploadStatus');
        statusDiv.className = type;
        statusDiv.textContent = message;
        
        if (type === 'success' || type === 'error') {
            setTimeout(() => {
                statusDiv.textContent = '';
                statusDiv.className = '';
            }, 5000);
        }
    }
    
    async startVersionChecking() {
        // Check version on startup
        await this.checkVersion();
        
        // Check version every 30 seconds
        setInterval(() => {
            this.checkVersion();
        }, 30000);
    }
    
    async checkVersion() {
        try {
            const response = await fetch(`${this.apiUrl}/version?t=${Date.now()}`, {
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            
            if (!response.ok) return;
            
            const versionData = await response.json();
            
            if (this.lastVersionCheck && this.lastVersionCheck !== versionData.cache_buster) {
                // Version has changed, show update notification
                console.log('🔄 New version detected!', versionData);
                this.showUpdateNotification();
                // Don't update lastVersionCheck here - only update after user refreshes
                return;
            }
            
            // Only set initial version check if not already set
            if (!this.lastVersionCheck) {
                this.lastVersionCheck = versionData.cache_buster;
            }
        } catch (error) {
            console.log('Version check failed:', error);
        }
    }
    
    showUpdateNotification() {
        // Create or update notification element
        let notification = document.getElementById('update-notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'update-notification';
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #FF9900;
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                z-index: 10000;
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 10px;
            `;
            document.body.appendChild(notification);
        }
        
        notification.innerHTML = `
            <span>🔄 A new version is available!</span>
            <button onclick="location.reload(true)" style="
                background: white;
                color: #FF9900;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
            ">Refresh Now</button>
        `;
        
        // Don't auto-hide - notification persists until user refreshes
    }
}

// Initialize the application
new DocReadStudio(); // Application starts itself