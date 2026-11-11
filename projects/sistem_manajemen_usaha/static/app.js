/**
 * Frontend logic for ACE Smart Enterprise Suite Dashboard
 */

let allTransactions = [];

function formatRupiah(num) {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0
  }).format(num);
}

async function loadDashboard() {
  try {
    const res = await fetch('/api/summary');
    if (!res.ok) throw new Error('Gagal mengambil ringkasan KPI');
    const data = await res.json();

    // Render KPI Cards
    document.getElementById('kpi-income').textContent = formatRupiah(data.total_income);
    document.getElementById('kpi-expense').textContent = formatRupiah(data.total_expense);
    document.getElementById('kpi-profit').textContent = formatRupiah(data.net_profit);
    document.getElementById('kpi-margin').textContent = `Margin Laba: ${data.profit_margin_pct}%`;
    document.getElementById('kpi-inventory-val').textContent = formatRupiah(data.inventory_asset_value);
    
    const warnEl = document.getElementById('kpi-stock-warning');
    if (data.low_stock_count > 0) {
      warnEl.textContent = `⚠️ ${data.low_stock_count} SKU Menipis / Kritis`;
      warnEl.style.color = '#f43f5e';
    } else {
      warnEl.textContent = 'Semua stok dalam batas aman';
      warnEl.style.color = '#10b981';
    }

    // Render 50-30-20 Progress Bar
    const b50 = data.budget_evaluation_50_30_20;
    const segNeeds = document.getElementById('seg-needs');
    const segWants = document.getElementById('seg-wants');
    const segSavings = document.getElementById('seg-savings');

    segNeeds.style.width = `${Math.min(b50.kebutuhan_operasional.pct, 100)}%`;
    segWants.style.width = `${Math.min(b50.pertumbuhan_dan_pemasaran.pct, 100)}%`;
    segSavings.style.width = `${Math.min(b50.cadangan_kas_dan_laba.pct, 100)}%`;

    // Render 50-30-20 Grid Cards
    const detailsGrid = document.getElementById('budget-details-grid');
    detailsGrid.innerHTML = `
      <div class="budget-box">
        <div class="budget-box-title">Kebutuhan Operasional (50%)</div>
        <div class="budget-box-val">${formatRupiah(b50.kebutuhan_operasional.amount)} <span class="badge ${b50.kebutuhan_operasional.status === 'IDEAL' ? 'badge-ideal' : 'badge-warn'}">${b50.kebutuhan_operasional.pct}%</span></div>
      </div>
      <div class="budget-box">
        <div class="budget-box-title">Pertumbuhan & Inovasi (30%)</div>
        <div class="budget-box-val">${formatRupiah(b50.pertumbuhan_dan_pemasaran.amount)} <span class="badge ${b50.pertumbuhan_dan_pemasaran.status === 'IDEAL' ? 'badge-ideal' : 'badge-warn'}">${b50.pertumbuhan_dan_pemasaran.pct}%</span></div>
      </div>
      <div class="budget-box">
        <div class="budget-box-title">Cadangan Kas & Laba Ditahan (20%)</div>
        <div class="budget-box-val">${formatRupiah(b50.cadangan_kas_dan_laba.amount)} <span class="badge ${b50.cadangan_kas_dan_laba.status === 'SEHAT' ? 'badge-ideal' : 'badge-warn'}">${b50.cadangan_kas_dan_laba.pct}%</span></div>
      </div>
    `;

    // Load sub-tables
    await loadProducts();
    await loadTransactions();
  } catch (err) {
    console.error('Error loading dashboard:', err);
  }
}

async function loadProducts() {
  const res = await fetch('/api/products');
  const data = await res.json();
  const tbody = document.getElementById('products-table-body');
  document.getElementById('product-count-badge').textContent = `${data.total} SKU`;

  if (!data.products || data.products.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">Belum ada produk.</td></tr>';
    return;
  }

  tbody.innerHTML = data.products.map(p => {
    const isCrit = p.stock <= p.min_stock;
    const badgeClass = isCrit ? 'badge-stock-crit' : 'badge-stock-safe';
    const statusText = isCrit ? (p.stock === 0 ? 'HABIS' : 'KRITIS') : 'AMAN';
    return `
      <tr>
        <td><code>${p.code}</code></td>
        <td><strong>${p.name}</strong></td>
        <td><span class="badge">${p.category}</span></td>
        <td>${formatRupiah(p.sell_price)}</td>
        <td><strong>${p.stock}</strong> (min ${p.min_stock})</td>
        <td><span class="${badgeClass}">${statusText}</span></td>
      </tr>
    `;
  }).join('');
}

async function loadTransactions() {
  const res = await fetch('/api/transactions');
  const data = await res.json();
  allTransactions = data.transactions || [];
  document.getElementById('tx-count-badge').textContent = `${allTransactions.length} Transaksi`;
  renderTransactionsTable(allTransactions);
}

function renderTransactionsTable(list) {
  const tbody = document.getElementById('tx-table-body');
  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Tidak ada catatan transaksi.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(tx => {
    const isIncome = tx.type === 'INCOME';
    const prefix = isIncome ? '+' : '-';
    const numClass = isIncome ? 'tx-income' : 'tx-expense';
    return `
      <tr>
        <td style="color: #94a3b8; font-size: 0.8rem;">${tx.timestamp}</td>
        <td>${tx.description}</td>
        <td><span class="badge">${tx.category}</span></td>
        <td style="font-size: 0.8rem;">${tx.payment_method}</td>
        <td class="${numClass}">${prefix} ${formatRupiah(tx.amount)}</td>
      </tr>
    `;
  }).join('');
}

function filterTransactions() {
  const q = document.getElementById('tx-search').value.toLowerCase().trim();
  if (!q) {
    renderTransactionsTable(allTransactions);
    return;
  }
  const filtered = allTransactions.filter(tx => 
    tx.description.toLowerCase().includes(q) ||
    tx.category.toLowerCase().includes(q) ||
    tx.ref_no.toLowerCase().includes(q)
  );
  renderTransactionsTable(filtered);
}

function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.style.display = 'flex';
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.style.display = 'none';
}

async function submitTransaction(e) {
  e.preventDefault();
  const payload = {
    type: document.getElementById('tx-type').value,
    category: document.getElementById('tx-cat').value,
    amount: parseFloat(document.getElementById('tx-amount').value),
    description: document.getElementById('tx-desc').value,
    payment_method: document.getElementById('tx-method').value,
  };

  try {
    const res = await fetch('/api/transactions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (result.success) {
      closeModal('modal-transaction');
      document.getElementById('form-tx').reset();
      await loadDashboard();
    } else {
      alert(`Gagal menyimpan: ${result.error}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

async function submitProduct(e) {
  e.preventDefault();
  const payload = {
    code: document.getElementById('p-code').value,
    name: document.getElementById('p-name').value,
    category: document.getElementById('p-cat').value,
    buy_price: parseFloat(document.getElementById('p-buy').value),
    sell_price: parseFloat(document.getElementById('p-sell').value),
    stock: parseInt(document.getElementById('p-stock').value),
    min_stock: parseInt(document.getElementById('p-min').value),
  };

  try {
    const res = await fetch('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (result.success) {
      closeModal('modal-product');
      document.getElementById('form-prod').reset();
      await loadDashboard();
    } else {
      alert(`Gagal menyimpan: ${result.error}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

function exportTransactionsCSV() {
  if (!allTransactions || allTransactions.length === 0) {
    alert('Tidak ada transaksi untuk diekspor');
    return;
  }
  const headers = ['Ref No', 'Tanggal', 'Tipe', 'Kategori', 'Nominal', 'Metode', 'Keterangan'];
  const rows = allTransactions.map(tx => [
    `"${tx.ref_no}"`,
    `"${tx.timestamp}"`,
    `"${tx.type}"`,
    `"${tx.category}"`,
    tx.amount,
    `"${tx.payment_method}"`,
    `"${tx.description.replace(/"/g, '""')}"`
  ]);
  const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `transaksi_enterprise_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Initial boot
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  // Auto refresh every 15s
  setInterval(loadDashboard, 15000);
});
