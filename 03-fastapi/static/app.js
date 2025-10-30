// Minimal SPA for todo app. Sends p_ prefixed args to /mobile01 RPC endpoints.
(function () {
    const $ = sel => document.querySelector(sel);
    const get = (sel) => document.getElementById(sel);

    const listsEl = get('lists');
    const tagsEl = get('tags');
    const tasksEl = get('tasks');
    const currentListTitle = get('current-list-title');
    const btnNewList = get('btn-new-list');
    const btnNewTask = get('btn-new-task');
    const btnCreateTag = get('btn-create-tag');

    const templates = {
        list: document.getElementById('list-item-tpl').content,
        task: document.getElementById('task-item-tpl').content
    };

    const state = {
        lists: [], tags: [], currentList: null
    };

    function authHeaders() {
        // Do not display or prompt for JWT in the UI. If a JWT is present in localStorage
        // under 'todo_jwt' we will send it. Otherwise calls are anonymous.
        const token = localStorage.getItem('todo_jwt');
        if (token) {
            const value = token.startsWith('Bearer') ? token : `Bearer ${token}`;
            return { 'Authorization': value, 'Content-Type': 'application/json' };
        }
        return { 'Content-Type': 'application/json' };
    }

    async function api(path, method = 'GET', body = null) {
        const headers = authHeaders();
        const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
        if (res.status === 204) return null;
        const txt = await res.text();
        try { return JSON.parse(txt); } catch (e) { return txt; }
    }

    // Lists
    async function loadLists() {
        state.lists = await api('/mobile01/lists') || [];
        renderLists();
    }

    function renderLists() {
        listsEl.innerHTML = '';
        state.lists.forEach(l => {
            const node = templates.list.cloneNode(true);
            const li = node.querySelector('li');
            const btn = node.querySelector('.select');
            node.querySelector('.title').textContent = l.title;
            li.classList.toggle('active', state.currentList && state.currentList.id === l.id);
            btn.onclick = () => { selectList(l); };
            listsEl.appendChild(li);
        });
    }

    async function selectList(list) {
        state.currentList = list;
        currentListTitle.textContent = list.title;
        btnNewTask.disabled = false;
        await loadTasks(list.id);
        renderLists();
    }

    async function createList() {
        const title = prompt('List title');
        if (!title) return;
        const color = '#7c3aed';
        const res = await api('/mobile01/lists', 'POST', { p_title: title, p_color: color, p_position: 0 });
        await loadLists();
        // auto-select
        if (res && res.id) selectList(res);
    }

    // Tasks
    async function loadTasks(listId) {
        const tasks = await api(`/mobile01/tasks?list_id=${encodeURIComponent(listId)}`) || [];
        state.tasks = tasks;
        renderTasks();
    }

    function renderTasks() {
        tasksEl.innerHTML = '';
        const list = state.currentList;
        if (!list) { tasksEl.classList.add('empty'); tasksEl.textContent = 'No list selected'; return; }
        tasksEl.classList.remove('empty');
        if (!state.tasks || state.tasks.length === 0) { tasksEl.textContent = 'No tasks'; return; }
        state.tasks.forEach(t => {
            const node = templates.task.cloneNode(true);
            const el = node.querySelector('.task-item');
            node.querySelector('.task-title').textContent = t.title;
            node.querySelector('.toggle-done').checked = !!t.completed_at;
            node.querySelector('.task-meta').textContent = (t.due_date ? ('Due: ' + t.due_date) : '') + (t.priority ? (' • P' + t.priority) : '');
            node.querySelector('.btn-delete').onclick = async () => { await api('/mobile01/tasks', 'DELETE', { p_id: t.id }); await loadTasks(list.id); };
            node.querySelector('.btn-edit').onclick = async () => {
                const newTitle = prompt('Edit task title', t.title); if (!newTitle) return;
                await api('/mobile01/tasks', 'PATCH', { p_id: t.id, p_title: newTitle }); await loadTasks(list.id);
            };
            node.querySelector('.toggle-done').onchange = async (ev) => {
                await api('/mobile01/tasks', 'PATCH', { p_id: t.id, p_completed_at: ev.target.checked ? new Date().toISOString() : null });
                await loadTasks(list.id);
            };
            tasksEl.appendChild(el);
        });
    }

    async function createTask() {
        if (!state.currentList) return alert('Select a list first');
        const title = prompt('Task title'); if (!title) return;
        await api('/mobile01/tasks', 'POST', { p_title: title, p_list_id: state.currentList.id });
        await loadTasks(state.currentList.id);
    }

    // Tags
    async function loadTags() {
        state.tags = await api('/mobile01/tags') || [];
        renderTags();
    }
    function renderTags() {
        tagsEl.innerHTML = '';
        state.tags.forEach(tag => {
            const li = document.createElement('li');
            li.textContent = tag.name + (tag.color ? (' • ' + tag.color) : '');
            tagsEl.appendChild(li);
        });
    }

    async function createTag() {
        const name = document.getElementById('tag-name').value.trim();
        const color = document.getElementById('tag-color').value.trim() || null;
        if (!name) return;
        await api('/mobile01/tags', 'POST', { p_name: name, p_color: color });
        document.getElementById('tag-name').value = ''; document.getElementById('tag-color').value = '';
        await loadTags();
    }

    // Wire events
    btnNewList.onclick = createList;
    btnNewTask.onclick = createTask;
    btnCreateTag.onclick = createTag;
    // Initial load
    (async function init() {
        await Promise.all([loadLists(), loadTags()]);
    })();

})();
