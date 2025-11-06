const socket = io();
let menu = [];
let cart = [];

socket.on('connect', () => {
    console.log('Connected to server');
});

const statusTranslations = {
    'pending': '待處理',
    'received': '已接單',
    'cooking': '烹調中',
    'ready': '已完成'
};

socket.on('order_updated', (order) => {
    const statusText = statusTranslations[order.status] || order.status;
    showNotification(`訂單 ${order.order_number} 狀態：${statusText}`, 'info');
});

async function loadMenu() {
    try {
        const response = await fetch('/api/menu');
        const data = await response.json();
        console.log('Menu data:', data);
        menu = Array.isArray(data) ? data : [];
        displayMenu();
    } catch (error) {
        console.error('Error loading menu:', error);
        showNotification('載入菜單時發生錯誤', 'danger');
    }
}

function displayMenu() {
    const container = document.getElementById('menu-container');
    if (!container) {
        console.error('Menu container not found');
        return;
    }
    container.innerHTML = '';
    if (menu.length === 0) {
        container.innerHTML = '<div class="col-12 text-center p-5 text-muted">目前菜單是空的。請前往 /admin 頁面新增菜單。</div>';
        return;
    }
    const categories = [...new Set(menu.map(item => item.category))];
    let html = '';
    categories.forEach(category => {
        html += `<div class="col-12 mt-4 mb-2"><h4 class="text-primary">${category}</h4><hr></div>`;
        const items = menu.filter(item => item.category === category);
        items.forEach(item => {
            html += `
                <div class="col-sm-6 col-md-4 col-lg-4">
                    <div class="card h-100 shadow-sm menu-item" style="cursor: pointer;" onclick="addToCart(${item.id})">
                        <div class="card-body d-flex flex-column">
                            <h5 class="card-title text-primary">${item.name}</h5>
                            <p class="card-text text-muted small">${item.description || '無介紹'}</p>
                            <div class="mt-auto d-flex justify-content-between align-items-center pt-2">
                                <span class="badge bg-secondary">${item.category}</span>
                                <span class="fs-5 fw-bold text-success">NT$ ${item.price.toFixed(2)}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
    });
    container.innerHTML = html;
}

function addToCart(itemId) {
    const menuItem = menu.find(item => item.id === itemId);
    if (!menuItem) {
        console.warn('Menu item not found:', itemId);
        return;
    }
    const existingItem = cart.find(item => item.id === itemId);
    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        cart.push({
            id: menuItem.id,
            name: menuItem.name,
            price: menuItem.price,
            quantity: 1,
            category: menuItem.category
        });
    }
    updateCart();
    showNotification(`已將 ${menuItem.name} 加入購物車`, 'success');
}

function updateCart() {
    const container = document.getElementById('cart-items');
    const submitBtn = document.getElementById('submit-order-btn');
    if (!container || !submitBtn) {
        console.error('Cart elements not found');
        return;
    }
    if (cart.length === 0) {
        container.innerHTML = '<p class="text-muted text-center py-4">購物車是空的。請從菜單新增項目。</p>';
        submitBtn.disabled = true;
        updateTotal();
        return;
    }
    let html = '';
    cart.forEach((item, index) => {
        html += `
            <div class="cart-item">
                <div class="cart-item-header">
                    <strong>${item.name}</strong>
                    <button class="btn btn-sm btn-danger" onclick="removeFromCart(${index})"><small>✕</small></button>
                </div>
                <div class="cart-item-controls">
                    <button class="btn btn-sm btn-outline-secondary qty-btn" onclick="decreaseQuantity(${index})">-</button>
                    <span class="quantity">${item.quantity}</span>
                    <button class="btn btn-sm btn-outline-secondary qty-btn" onclick="increaseQuantity(${index})">+</button>
                    <span class="ms-auto text-success fw-bold">NT$ ${(item.price * item.quantity).toFixed(2)}</span>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
    submitBtn.disabled = false;
    updateTotal();
}

function increaseQuantity(index) {
    cart[index].quantity += 1;
    updateCart();
}

function decreaseQuantity(index) {
    if (cart[index].quantity > 1) {
        cart[index].quantity -= 1;
        updateCart();
    }
}

function removeFromCart(index) {
    cart.splice(index, 1);
    updateCart();
}

function updateTotal() {
    const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const totalElement = document.getElementById('cart-total');
    if (totalElement) {
        totalElement.textContent = `NT$ ${total.toFixed(2)}`;
        calculateChange();
    } else {
        console.error('Cart total element not found');
    }
}

function calculateChange() {
    const totalElement = document.getElementById('cart-total');
    const paymentInput = document.getElementById('payment-amount');
    const changeSpan = document.getElementById('change-amount');
    const errorSpan = document.getElementById('payment-error');
    if (!totalElement || !paymentInput || !changeSpan || !errorSpan) {
        console.error('Payment elements not found');
        return;
    }
    const total = parseFloat(totalElement.textContent.replace('NT$', '').trim()) || 0;
    const payment = parseFloat(paymentInput.value) || 0;
    const change = payment - total;
    if (change >= 0) {
        changeSpan.textContent = `找零：NT$ ${change.toFixed(2)}`;
        errorSpan.textContent = '';
    } else {
        changeSpan.textContent = `找零：NT$ 0.00`;
        errorSpan.textContent = `付款不足 NT$ ${(-change).toFixed(2)}`;
    }
}

function clearCart() {
    cart = [];
    updateCart();
    const notesInput = document.getElementById('order-notes');
    if (notesInput) notesInput.value = '';
    calculateChange();
}

async function submitOrder() {
    console.log('Submitting order...'); // 調試開始
    if (cart.length === 0) {
        showNotification('購物車是空的！', 'warning');
        return;
    }
    const notes = document.getElementById('order-notes')?.value || '';
    const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const paymentInput = document.getElementById('payment-amount');
    const payment = paymentInput ? parseFloat(paymentInput.value) || 0 : 0;
    if (payment < total) {
        showNotification('付款金額不足，無法提交！', 'danger');
        return;
    }
    const orderData = {
        items: cart.map(item => ({
            id: item.id,
            name: item.name,
            price: item.price,
            quantity: item.quantity,
            category: item.category
        })),
        total_amount: total,
        notes: notes
    };
    console.log('Order data:', orderData); // 調試數據
    try {
        const response = await fetch('/api/orders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });
        console.log('Response status:', response.status); // 調試狀態
        const result = await response.json();
        document.getElementById('modal-order-number').textContent = result.order.order_number;
        const modal = new bootstrap.Modal(document.getElementById('orderSuccessModal'));
        modal.show();
        clearCart();
    } catch (error) {
        console.error('Error submitting order:', error);
        showNotification('送出訂單時發生錯誤', 'danger');
    }
}

function showNotification(message, type = 'info') {
    const container = document.getElementById('order-status');
    if (!container) {
        console.error('Notification container not found');
        return;
    }
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    container.appendChild(alert);
    setTimeout(() => alert.remove(), 3000);
}

document.getElementById('submit-order-btn').addEventListener('click', submitOrder);
document.getElementById('clear-cart-btn').addEventListener('click', clearCart);
const paymentInput = document.getElementById('payment-amount');
if (paymentInput) {
    paymentInput.addEventListener('input', calculateChange);
} else {
    console.error('Payment input not found');
}
loadMenu();
