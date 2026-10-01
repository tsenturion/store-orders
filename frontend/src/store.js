import { computed, reactive, ref, watch } from 'vue';

export const user = ref(null);
export const csrf = ref('');
export const authReady = ref(false);
export const products = ref([]);
export const categories = ref([]);
export const catalogError = ref('');
export const toasts = ref([]);
let savedCart = [];
try {
  savedCart = JSON.parse(localStorage.getItem('polka.cart') || '[]');
} catch {
  /* Некорректная корзина восстанавливается пустой. */
}
export const cart = ref(
  Array.isArray(savedCart)
    ? savedCart.filter(
        (x) => Number.isInteger(x.id) && Number.isInteger(x.quantity) && x.quantity > 0 && x.quantity <= 100,
      )
    : [],
);
export const checkoutKey = ref(localStorage.getItem('polka.checkoutKey') || crypto.randomUUID());
export const cartLines = computed(() =>
  cart.value
    .map((line) => ({ ...line, product: products.value.find((p) => p.id === line.id) }))
    .filter((line) => line.product),
);
export const cartCount = computed(() => cart.value.reduce((total, line) => total + line.quantity, 0));
export const cartTotal = computed(() =>
  cartLines.value.reduce((total, line) => total + Number(line.product.price) * line.quantity, 0),
);
export const isCustomer = computed(() => user.value?.role === 'customer');
export const isStaff = computed(() => ['warehouse', 'manager'].includes(user.value?.role));
export const isManager = computed(() => user.value?.role === 'manager');
export const money = (value) =>
  new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number(value));
export const timestamp = (value) =>
  new Date(value).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  });
export const imageUrl = (image) => `${import.meta.env.BASE_URL}images/${image}.svg`;
export const statusClass = (status) =>
  ({
    created: 'bg-stone-100 text-stone-600',
    queued: 'bg-amber-50 text-amber-800',
    picking: 'bg-blue-50 text-blue-700',
    ready: 'bg-teal-50 text-teal-700',
    shipped: 'bg-purple-50 text-purple-700',
    delivered: 'bg-green-50 text-green-700',
    cancelled: 'bg-red-50 text-red-700',
  })[status] || '';

watch(cart, (value) => localStorage.setItem('polka.cart', JSON.stringify(value)), { deep: true });
watch(checkoutKey, (value) => localStorage.setItem('polka.checkoutKey', value));

export function notify(text, error = false) {
  const id = crypto.randomUUID();
  toasts.value.push({ id, text, error });
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }, 4500);
}

export async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(path, {
      credentials: 'same-origin',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(csrf.value ? { 'X-CSRF-Token': csrf.value } : {}),
        ...options.headers,
      },
      signal: controller.signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      if (response.status === 401 && !path.endsWith('/login')) {
        user.value = null;
        csrf.value = '';
      }
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось выполнить действие');
    }
    return response.status === 204 ? null : response.json();
  } catch (error) {
    if (error.name === 'AbortError' || error instanceof TypeError)
      throw new Error('Нет связи с сервером. Повторите действие');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function restoreSession() {
  try {
    const data = await api('/api/auth/me');
    user.value = data.user;
    csrf.value = data.csrf;
  } catch {
    /* Гостю доступна витрина. */
  }
  authReady.value = true;
}

export async function loadProducts() {
  try {
    const data = await api('/api/products');
    products.value = data.products;
    categories.value = data.categories;
    catalogError.value = '';
  } catch (error) {
    catalogError.value = error.message;
  }
}

export function addToCart(product, quantity = 1) {
  const line = cart.value.find((x) => x.id === product.id);
  const total = (line?.quantity || 0) + quantity;
  if (total > product.available || total > 100) {
    notify('Больше товара нет в наличии', true);
    return;
  }
  if (line) line.quantity = total;
  else cart.value.push({ id: product.id, quantity });
  checkoutKey.value = crypto.randomUUID();
  notify('Товар добавлен в корзину');
}

export function changeQuantity(id, delta) {
  const line = cart.value.find((x) => x.id === id);
  if (!line) return;
  const available = products.value.find((x) => x.id === id)?.available || 0;
  if (delta > 0 && line.quantity + delta > Math.min(100, available)) {
    notify('Больше товара нет в наличии', true);
    return;
  }
  line.quantity += delta;
  if (line.quantity <= 0) cart.value = cart.value.filter((x) => x.id !== id);
  checkoutKey.value = crypto.randomUUID();
}

export async function download(path, filename) {
  try {
    const response = await fetch(path, { method: 'HEAD', credentials: 'same-origin' });
    if (!response.ok) {
      const failure = await fetch(path, { credentials: 'same-origin' });
      const result = await failure.json().catch(() => ({}));
      throw new Error(result.detail || 'Не удалось подготовить файл');
    }
    const link = document.createElement('a');
    link.href = path;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    notify('Скачивание файла началось');
  } catch (error) {
    notify(error instanceof TypeError ? 'Нет связи с сервером' : error.message, true);
  }
}

export function usePolling(loader, milliseconds = 5000) {
  const state = reactive({ loading: true, error: '', busy: false });
  let running = false;
  let timer;
  let disposed = false;
  async function refresh() {
    if (running || disposed) return;
    running = true;
    try {
      await loader();
      state.error = '';
    } catch (error) {
      if (!disposed) state.error = error.message;
    } finally {
      running = false;
      state.loading = false;
    }
  }
  return {
    state,
    refresh,
    start() {
      disposed = false;
      refresh();
      timer = setInterval(refresh, milliseconds);
    },
    stop() {
      disposed = true;
      clearInterval(timer);
    },
  };
}
