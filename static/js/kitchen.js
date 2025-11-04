let orders = [];
let currentFilter = 'all';
let socket;

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed bottom-0 end-0 m-3`;
    alertDiv.style.zIndex = 1000;
    alertDiv.innerHTML = `${message} <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 3000);
}

function getStatusBadge(status) {
    const badges = {
        'pending': '<span class="badge bg-warning">待處理</span>',
        'received': '<span class="badge bg-info">已接單</span>',
        'cooking': '<span class="badge bg-primary">烹調中</span>',
        'ready': '<span class="badge bg-success">準備好</span>',
        'completed': '<span class="badge bg-secondary">已完成</span>'
    };
    return badges[status] || '<span class="badge bg-secondary">未知</span>';
}

function getStatusButtons(order) {
    switch (order.status) {
        case 'pending':
            return `
                <button class="btn btn-info btn-sm" onclick="updateStatus(${order.id}, 'received')">
                    👀 接單
                </button>
            `;
        case 'received':
            return `
                <button class="btn btn-primary btn-sm" onclick="updateStatus(${order.id}, 'cooking')">
                    🍳 開始烹調
                </button>
            `;
        case 'cooking':
            return `
                <button class="btn btn-success btn-sm" onclick="updateStatus(${order.id}, 'ready')">
                    ✅ 標記完成
                </button>
            `;
        case 'ready':
            return `
                <button class="btn btn-secondary btn-sm" onclick="updateStatus(${order.id}, 'completed')">
                    ✔️ 訂單送達
                </button>
            `;
        default:
            return '';
    }
}

async function confirmDeleteOrder(orderId) {
    if (confirm('確定要刪除此訂單嗎？此操作無法復原！')) {
        try {
            const response = await fetch(`/api/orders/${orderId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) {
                throw new Error(response.status === 404 ? '訂單可能已不存在' : `刪除訂單失敗: ${response.status}`);
            }
            showAlert('訂單已成功刪除', 'success');
        } catch (error) {
            console.error('刪除訂單錯誤:', error.message);
            showAlert(`刪除訂單失敗: ${error.message}`, 'danger');
            if (error.message.includes('404')) {
                loadOrders();
            }
        }
    }
}

async function loadOrders() {
    try {
        const url = `/api/orders?filter=${currentFilter}`;
        console.log('正在載入訂單:', url);
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`載入訂單失敗: ${response.status}`);
        }
        orders = await response.json();
        console.log('收到訂單:', orders);
        for (let order of orders) {
            if (typeof order.items === 'string') {
                order.items = JSON.parse(order.items);
            }
            console.log('訂單時間檢查:', order.id, 'created_at:', order.created_at);
        }
        orders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        displayOrders();
    } catch (error) {
        console.error('載入訂單錯誤:', error.message);
        showAlert('載入訂單時發生錯誤', 'danger');
    }
}

function formatOrderTime(createdAt) {
    try {
        const date = new Date(createdAt);
        if (isNaN(date.getTime())) {
            console.error('無效的 created_at 格式:', createdAt);
            return '無效時間';
        }
        const formatter = new Intl.DateTimeFormat('zh-TW', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false,
            timeZone: 'Asia/Taipei'
        });
        const formattedTime = formatter.format(date);
        console.log('格式化時間:', createdAt, '->', formattedTime);
        return formattedTime;
    } catch (error) {
        console.error('時間格式化錯誤:', error.message, 'createdAt:', createdAt);
        return '時間格式錯誤';
    }
}

function displayOrders() {
    const container = document.getElementById('orders-container');
    const noOrders = document.getElementById('no-orders');
    
    let filteredOrders = orders;
    if (currentFilter !== 'all') {
        filteredOrders = orders.filter(order => order.status === currentFilter);
    }
    
    const pendingCount = orders.filter(o => o.status === 'pending').length;
    document.getElementById('pending-count').textContent = `${pendingCount} 待處理`;
    
    if (filteredOrders.length === 0) {
        container.innerHTML = '';
        noOrders.classList.remove('d-none');
        return;
    }
    
    noOrders.classList.add('d-none');
    
    let html = '';
    filteredOrders.forEach(order => {
        const statusClass = `status-${order.status}`;
        const orderTime = formatOrderTime(order.created_at);
        
        html += `
            <div class="col-lg-4 col-md-6">
                <div class="order-card ${statusClass}">
                    <div class="order-header">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="order-number">${order.order_number}</div>
                            ${getStatusBadge(order.status)}
                        </div>
                        <div class="order-time">⏰ ${orderTime}</div>
                    </div>
                    
                    <div class="order-items">
                        <h6>項目：</h6>
                        ${order.items.map(item => `
                            <div class="order-item">
                                <div class="d-flex justify-content-between">
                                    <span>${item.quantity}x ${item.name}</span>
                                    <span class="text-success">$${(item.price * item.quantity).toFixed(2)}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    
                    ${order.notes ? `<div class="alert alert-info mt-2 mb-2"><small><strong>備註：</strong> ${order.notes}</small></div>` : ''}
                    
                    <div class="mt-3 mb-2">
                        <strong>總計：<span class="order-total">$${order.total_amount.toFixed(2)}</span></strong>
                    </div>
                    
                    <div class="status-buttons mt-3">
                        ${getStatusButtons(order)}
                    </div>
                    <div class="mt-2">
                        <button class="btn btn-danger btn-sm" onclick="confirmDeleteOrder(${order.id})">
                            🗑️ 刪除訂單
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function updateStatus(orderId, newStatus) {
    try {
        const response = await fetch(`/api/orders/${orderId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        if (!response.ok) {
            throw new Error(response.status === 404 ? '訂單可能已不存在' : `更新狀態失敗: ${response.status}`);
        }
        showAlert('訂單狀態更新成功', 'success');
    } catch (error) {
        console.error('更新狀態錯誤:', error.message);
        showAlert(`更新狀態失敗: ${error.message}`, 'danger');
        if (error.message.includes('404')) {
            loadOrders();
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    socket = io();

    socket.on('connect', () => {
        console.log('連接到伺服器');
        loadOrders();
        setInterval(loadOrders, 60000);
    });

    socket.on('new_order', (order) => {
        console.log('收到新訂單:', order);
        if (typeof order.items === 'string') {
            order.items = JSON.parse(order.items);
        }
        orders.unshift(order);
        orders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        displayOrders();
        showAlert('收到新訂單！', 'success');
    });

    socket.on('order_updated', (updatedOrder) => {
        console.log('訂單更新:', updatedOrder);
        if (typeof updatedOrder.items === 'string') {
            updatedOrder.items = JSON.parse(updatedOrder.items);
        }
        const index = orders.findIndex(order => order.id === updatedOrder.id);
        if (index !== -1) {
            orders[index] = updatedOrder;
        } else {
            orders.push(updatedOrder);
        }
        orders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        displayOrders();
    });

    socket.on('order_deleted', (data) => {
        console.log('訂單刪除:', data);
        orders = orders.filter(order => order.id !== data.order_id);
        displayOrders();
        showAlert('訂單已刪除', 'success');
    });

    socket.on('connect_error', (error) => {
        console.error('連線錯誤:', error);
        showAlert('無法連接到伺服器，請檢查網絡', 'danger');
    });

    document.querySelectorAll('input[name="filter"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentFilter = e.target.value;
            displayOrders();
        });
    });
});

