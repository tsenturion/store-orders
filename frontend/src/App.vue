<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import {
  ShoppingBag,
  Search,
  ArrowUpRight,
  UserRound,
  LogOut,
  Bell,
  X,
  Plus,
  Truck,
  PackageCheck,
  Leaf,
  Check,
  Menu,
} from '@lucide/vue';
import AuthModal from './components/AuthModal.vue';
import CartDrawer from './components/CartDrawer.vue';
import OrdersView from './components/OrdersView.vue';
import WarehouseView from './components/WarehouseView.vue';
import ManagerView from './components/ManagerView.vue';
import {
  api,
  user,
  csrf,
  restoreSession,
  products,
  categories,
  catalogError,
  loadProducts,
  cartCount,
  isStaff,
  isManager,
  money,
  imageUrl,
  addToCart,
  toasts,
  notify,
  timestamp,
} from './store';
const route = ref(location.hash.slice(1) || 'catalog');
const query = ref('');
const category = ref('Все вещи');
const sort = ref('default');
const loading = ref(true);
const loginOpen = ref(false);
const cartOpen = ref(false);
const mobileMenu = ref(false);
const notificationsOpen = ref(false);
const notifications = ref([]);
const notificationError = ref('');
const detail = ref(null);
const detailDialog = ref(null);
let notificationTimer;
let notificationBusy = false;
const navigation = computed(() => [
  { id: 'catalog', label: 'Каталог' },
  ...(user.value ? [{ id: 'orders', label: isStaff.value ? 'Заказы' : 'Мои заказы' }] : []),
  ...(isStaff.value ? [{ id: 'warehouse', label: 'Склад' }] : []),
  ...(isManager.value ? [{ id: 'manager', label: 'Управление' }] : []),
]);
const view = computed(() => (navigation.value.some((x) => x.id === route.value) ? route.value : 'catalog'));
const unread = computed(() => notifications.value.filter((n) => !n.read).length);
const filtered = computed(() => {
  const values = products.value.filter(
    (p) =>
      (category.value === 'Все вещи' || p.category === category.value) &&
      `${p.name} ${p.description}`.toLowerCase().includes(query.value.toLowerCase()),
  );
  if (sort.value === 'price-up') return values.sort((a, b) => Number(a.price) - Number(b.price));
  if (sort.value === 'price-down') return values.sort((a, b) => Number(b.price) - Number(a.price));
  return values;
});
const roleName = computed(
  () => ({ customer: 'Покупатель', warehouse: 'Сотрудник склада', manager: 'Менеджер' })[user.value?.role],
);
function navigate(id) {
  location.hash = id;
  mobileMenu.value = false;
}
function scrollCollection() {
  document.getElementById('collection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function hashChanged() {
  route.value = location.hash.slice(1) || 'catalog';
  loadProducts();
  window.scrollTo({ top: 0, behavior: 'instant' });
}
async function fetchNotifications() {
  if (!user.value || notificationBusy) return;
  notificationBusy = true;
  try {
    notifications.value = await api('/api/notifications');
    notificationError.value = '';
  } catch (err) {
    notificationError.value = err.message;
  } finally {
    notificationBusy = false;
  }
}
watch(user, (value) => {
  notifications.value = [];
  clearInterval(notificationTimer);
  if (value) {
    fetchNotifications();
    notificationTimer = setInterval(fetchNotifications, 5000);
  } else notificationsOpen.value = false;
});
async function logout() {
  try {
    await api('/api/auth/logout', { method: 'POST' });
    user.value = null;
    csrf.value = '';
    navigate('catalog');
    notify('Вы вышли из аккаунта');
  } catch (err) {
    notify(err.message, true);
  }
}
async function markRead() {
  try {
    await api('/api/notifications/read', { method: 'POST' });
    await fetchNotifications();
  } catch (err) {
    notify(err.message, true);
  }
}
function showProduct(product) {
  detail.value = product;
  detailDialog.value.showModal();
}
onMounted(async () => {
  window.addEventListener('hashchange', hashChanged);
  await Promise.all([restoreSession(), loadProducts()]);
  loading.value = false;
});
onUnmounted(() => {
  window.removeEventListener('hashchange', hashChanged);
  clearInterval(notificationTimer);
});
</script>

<template>
  <div class="flex min-h-dvh flex-col">
    <div class="bg-ink px-4 py-2.5 text-center text-[11px] tracking-wide text-white/85">
      Хорошие вещи для вашего дома
      <span class="mx-3 text-white/30">·</span>
      Доставка без доплаты
    </div>
    <header class="sticky top-0 z-30 border-b border-stone-200 bg-paper/95 backdrop-blur-md">
      <div class="mx-auto flex h-21 max-w-7xl items-center justify-between gap-5 px-5 md:px-8">
        <a href="#catalog" class="flex items-center gap-3" aria-label="Полка — главная">
          <span
            class="flex h-9 w-9 items-center justify-center rounded-full border border-ink/30 font-display text-2xl"
          >
            п
          </span>
          <span class="text-xl font-semibold tracking-[.2em]">ПОЛКА</span>
        </a>
        <nav class="hidden items-center gap-7 lg:flex" aria-label="Главное меню">
          <a
            v-for="item in navigation"
            :key="item.id"
            :href="`#${item.id}`"
            class="border-b py-2 text-sm"
            :class="
              view === item.id ? 'border-ink font-semibold' : 'border-transparent text-muted hover:text-ink'
            "
          >
            {{ item.label }}
          </a>
        </nav>
        <div class="flex items-center gap-2 md:gap-4">
          <div v-if="user" class="relative">
            <button
              class="relative rounded-full p-2"
              :aria-expanded="notificationsOpen"
              aria-label="Уведомления"
              @click="
                notificationsOpen = !notificationsOpen;
                if (notificationsOpen) fetchNotifications();
              "
            >
              <Bell :size="19" />
              <span v-if="unread" class="absolute right-1 top-1 h-2 w-2 rounded-full bg-accent" />
            </button>
            <div
              v-if="notificationsOpen"
              class="absolute right-[-55px] top-12 w-[min(350px,90vw)] rounded-xl border border-stone-200 bg-white shadow-xl md:right-0"
            >
              <div class="flex items-center justify-between border-b border-stone-100 p-4">
                <h2 class="font-semibold">Уведомления</h2>
                <button v-if="unread" class="text-xs text-accent" @click="markRead">Прочитать все</button>
              </div>
              <p v-if="notificationError" role="alert" class="p-4 text-sm text-red-700">
                {{ notificationError }}
              </p>
              <p v-else-if="!notifications.length" class="p-8 text-center text-sm text-muted">
                Здесь появятся новости о заказах
              </p>
              <div class="max-h-80 overflow-y-auto">
                <button
                  v-for="n in notifications"
                  :key="n.id"
                  class="block w-full border-b border-stone-100 p-4 text-left text-sm hover:bg-paper"
                  :class="!n.read ? 'bg-paper/60' : ''"
                  @click="
                    navigate('orders');
                    notificationsOpen = false;
                  "
                >
                  <p>{{ n.text }}</p>
                  <p class="mt-1 text-xs text-muted">{{ timestamp(n.created_at) }}</p>
                </button>
              </div>
            </div>
          </div>
          <button
            v-if="!user"
            class="flex items-center gap-2 p-2 text-sm"
            aria-label="Войти"
            @click="loginOpen = true"
          >
            <UserRound :size="19" />
            <span class="hidden sm:inline">Войти</span>
          </button>
          <div v-else class="hidden items-center gap-3 sm:flex">
            <div class="text-right">
              <p class="max-w-32 truncate text-xs font-semibold">{{ user.name }}</p>
              <p class="mt-0.5 text-[10px] text-muted">{{ roleName }}</p>
            </div>
            <button class="p-2 text-muted hover:text-ink" aria-label="Выйти из аккаунта" @click="logout">
              <LogOut :size="17" />
            </button>
          </div>
          <button
            v-if="!isStaff"
            class="flex items-center gap-2 rounded-full border border-stone-300 px-3.5 py-2.5 text-sm"
            aria-label="Открыть корзину"
            @click="cartOpen = true"
          >
            <ShoppingBag :size="18" />
            <span class="hidden sm:inline">Корзина</span>
            <span
              v-if="cartCount"
              class="flex h-5 min-w-5 items-center justify-center rounded-full bg-ink px-1 text-[10px] text-white"
            >
              {{ cartCount }}
            </span>
          </button>
          <button
            class="p-2 lg:hidden"
            aria-label="Открыть меню"
            :aria-expanded="mobileMenu"
            @click="mobileMenu = !mobileMenu"
          >
            <Menu :size="21" />
          </button>
        </div>
      </div>
      <nav
        v-if="mobileMenu"
        class="border-t border-stone-200 px-5 pb-4 lg:hidden"
        aria-label="Мобильное меню"
      >
        <a
          v-for="item in navigation"
          :key="item.id"
          :href="`#${item.id}`"
          class="block py-3 text-sm"
          @click="mobileMenu = false"
        >
          {{ item.label }}
        </a>
        <button
          v-if="user"
          class="py-3 text-sm text-accent"
          @click="
            logout();
            mobileMenu = false;
          "
        >
          Выйти · {{ user.name }}
        </button>
      </nav>
    </header>
    <main class="flex-1">
      <template v-if="view === 'catalog'">
        <section
          v-if="!query && category === 'Все вещи'"
          class="mx-auto grid max-w-7xl gap-6 px-5 pb-10 pt-8 md:px-8 lg:grid-cols-[1fr_1.08fr] lg:gap-8 lg:pt-12"
        >
          <div class="flex flex-col justify-center py-6 lg:py-10">
            <p class="eyebrow text-accent">Маленькие детали. Большое чувство дома.</p>
            <h1
              class="mt-6 max-w-xl font-display text-[clamp(40px,4.8vw,64px)] leading-[1.08] tracking-[-.025em]"
            >
              Уют начинается
              <br />
              с простых вещей
              <span class="text-accent">.</span>
            </h1>
            <p class="mt-6 max-w-sm text-sm leading-7 text-muted md:text-base">
              Продуманные формы, тёплые фактуры и вещи, которые хочется оставить рядом.
            </p>
            <div class="mt-8">
              <a href="#collection" class="primary !rounded-full !px-6" @click.prevent="scrollCollection">
                Найти своё
                <ArrowUpRight :size="18" />
              </a>
            </div>
            <div class="mt-9 flex items-center gap-3 text-xs text-muted">
              <span class="h-px w-8 bg-stone-300" />
              Для каждого уголка вашего дома
            </div>
          </div>
          <div class="relative min-h-[330px] overflow-hidden rounded-[24px] bg-[#e8e4da]">
            <img
              :src="imageUrl('hero')"
              alt="Тёплый свет настольной лампы, керамическая ваза и чашка на деревянной полке"
              class="h-full min-h-[330px] w-full object-cover"
            />
            <div
              class="absolute bottom-5 left-5 flex items-center gap-3 rounded-full bg-paper/90 px-4 py-2.5 backdrop-blur-sm"
            >
              <span class="h-1.5 w-1.5 rounded-full bg-accent" />
              <span class="text-xs">Коллекция для спокойных дней</span>
            </div>
            <span
              class="absolute right-5 top-5 rounded-full border border-white/70 bg-white/20 px-3 py-1.5 text-[10px] tracking-widest"
            >
              ВЫБРАНО С ЗАБОТОЙ
            </span>
          </div>
        </section>
        <section id="collection" class="mx-auto max-w-7xl scroll-mt-28 px-5 pb-14 pt-5 md:px-8">
          <div class="flex flex-wrap items-end justify-between gap-5">
            <div>
              <p class="eyebrow text-muted">Создайте пространство для себя</p>
              <h2 class="mt-3 font-display text-3xl md:text-4xl">Вещи с характером</h2>
            </div>
            <span class="text-xs text-muted">
              {{ filtered.length }}
              {{
                filtered.length === 1
                  ? 'товар'
                  : filtered.length > 1 && filtered.length < 5
                    ? 'товара'
                    : 'товаров'
              }}
            </span>
          </div>
          <div class="mt-7 flex flex-wrap items-center justify-between gap-4 border-y border-stone-200 py-4">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="c in ['Все вещи', ...categories]"
                :key="c"
                class="rounded-full px-4 py-2 text-xs transition-colors"
                :class="category === c ? 'bg-ink text-white' : 'bg-white text-muted hover:bg-stone-200'"
                @click="category = c"
              >
                {{ c }}
              </button>
            </div>
            <div class="flex w-full gap-3 lg:w-auto">
              <div class="relative flex-1 lg:w-52">
                <Search :size="15" class="absolute left-3 top-3 text-muted" />
                <input
                  v-model="query"
                  type="search"
                  aria-label="Поиск по каталогу"
                  placeholder="Найти вещь…"
                  class="!rounded-full !py-2 !pl-9 text-xs"
                />
              </div>
              <select
                v-model="sort"
                aria-label="Сортировка товаров"
                class="!w-40 !rounded-full !py-2 text-xs"
              >
                <option value="default">По умолчанию</option>
                <option value="price-up">Сначала дешевле</option>
                <option value="price-down">Сначала дороже</option>
              </select>
            </div>
          </div>
          <div
            v-if="catalogError"
            role="alert"
            class="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl bg-red-50 p-5 text-sm text-red-700"
          >
            <p>{{ catalogError }}</p>
            <button class="secondary" @click="loadProducts">Повторить</button>
          </div>
          <div v-if="loading" class="mt-7 grid grid-cols-2 gap-5 lg:grid-cols-4">
            <div v-for="n in 4" :key="n" class="h-80 animate-pulse rounded-2xl bg-stone-200/70" />
          </div>
          <div v-else class="mt-7 grid grid-cols-2 gap-x-5 gap-y-9 md:gap-x-6 lg:grid-cols-4">
            <article v-for="product in filtered" :key="product.id" class="group min-w-0">
              <button
                class="relative block aspect-[1/1.05] w-full overflow-hidden rounded-2xl bg-[#e9e6df] text-left"
                :aria-label="`Подробнее: ${product.name}`"
                @click="showProduct(product)"
              >
                <img
                  :src="imageUrl(product.image)"
                  :alt="product.name"
                  class="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                  loading="lazy"
                />
                <span
                  v-if="product.available < 5"
                  class="absolute left-3 top-3 rounded-full bg-paper/90 px-2.5 py-1 text-[10px]"
                >
                  {{ product.available ? 'Последние экземпляры' : 'Скоро вернётся' }}
                </span>
                <span
                  class="absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-full bg-white/80 text-ink opacity-0 transition-opacity group-hover:opacity-100"
                >
                  <ArrowUpRight :size="15" />
                </span>
              </button>
              <p class="mt-4 text-[10px] uppercase tracking-[.14em] text-muted">{{ product.category }}</p>
              <button
                class="mt-1.5 text-left text-sm font-semibold md:text-[15px]"
                @click="showProduct(product)"
              >
                {{ product.name }}
              </button>
              <div class="mt-3 flex items-center justify-between gap-2">
                <p class="text-sm md:text-base">{{ money(product.price) }}</p>
                <button
                  v-if="!isStaff"
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-stone-300 hover:bg-ink hover:text-white"
                  :disabled="!product.available"
                  :aria-label="`В корзину: ${product.name}`"
                  @click="addToCart(product)"
                >
                  <Plus :size="17" />
                </button>
                <span v-else class="text-[11px] text-muted">{{ product.available }} шт.</span>
              </div>
            </article>
          </div>
          <div v-if="!loading && !filtered.length && !catalogError" class="py-16 text-center">
            <Search :size="32" class="mx-auto text-stone-400" />
            <h3 class="mt-4 font-display text-2xl">Таких вещей пока нет</h3>
            <p class="mt-2 text-sm text-muted">Попробуйте другое название или категорию.</p>
            <button
              class="secondary mt-5"
              @click="
                query = '';
                category = 'Все вещи';
              "
            >
              Сбросить поиск
            </button>
          </div>
        </section>
        <section class="border-y border-stone-200 bg-[#eeeee6]">
          <div class="mx-auto grid max-w-7xl gap-7 px-5 py-10 md:grid-cols-3 md:px-8">
            <div
              v-for="[icon, title, text] in [
                [Truck, 'Без лишних расходов', 'Доставка без доплаты, оплата при получении'],
                [PackageCheck, 'Внимание к каждой детали', 'Проверяем комплектность перед отправкой'],
                [Leaf, 'Вещи надолго', 'Удобные формы и спокойные цвета'],
              ]"
              :key="title"
              class="flex items-start gap-4"
            >
              <component :is="icon" :size="23" stroke-width="1.3" class="mt-0.5 shrink-0 text-accent" />
              <div>
                <h3 class="text-sm font-semibold">{{ title }}</h3>
                <p class="mt-2 text-xs leading-5 text-muted">{{ text }}</p>
              </div>
            </div>
          </div>
        </section>
      </template>
      <OrdersView v-else-if="view === 'orders'" :key="user.id" />
      <WarehouseView v-else-if="view === 'warehouse'" :key="user.id" />
      <ManagerView v-else-if="view === 'manager'" :key="user.id" />
    </main>
    <footer
      class="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-5 px-5 py-8 text-xs text-muted md:px-8"
    >
      <div>
        <span class="font-semibold tracking-[.18em] text-ink">ПОЛКА</span>
        <span class="ml-4">Дом — в деталях.</span>
      </div>
      <p>Каталог · Доставка · Забота о вашем доме</p>
      <span>© {{ new Date().getFullYear() }} Полка</span>
    </footer>
    <AuthModal :open="loginOpen" @close="loginOpen = false" />
    <CartDrawer
      :open="cartOpen"
      @close="cartOpen = false"
      @login="loginOpen = true"
      @ordered="navigate('orders')"
    />
    <dialog
      ref="detailDialog"
      class="m-auto w-[min(780px,92vw)] overflow-y-auto rounded-2xl border-0 p-0 shadow-xl backdrop:bg-ink/40"
      aria-labelledby="detail-title"
    >
      <div v-if="detail" class="relative grid md:grid-cols-2">
        <button
          class="absolute right-4 top-4 z-10 rounded-full bg-white/90 p-2"
          aria-label="Закрыть карточку товара"
          @click="detailDialog.close()"
        >
          <X :size="19" />
        </button>
        <img :src="imageUrl(detail.image)" :alt="detail.name" class="h-full min-h-60 w-full object-cover" />
        <div class="flex flex-col justify-center p-8">
          <p class="eyebrow text-accent">{{ detail.category }}</p>
          <h2 id="detail-title" class="mt-4 font-display text-3xl">{{ detail.name }}</h2>
          <p class="mt-5 text-sm leading-7 text-muted">{{ detail.description }}</p>
          <p class="mt-6 text-2xl font-semibold">{{ money(detail.price) }}</p>
          <p class="mt-2 text-xs text-muted">
            {{ detail.available ? `В наличии: ${detail.available} шт.` : 'Сейчас нет в наличии' }} ·
            {{ detail.sku }}
          </p>
          <button
            v-if="!isStaff"
            class="primary mt-6"
            :disabled="!detail.available"
            @click="
              addToCart(detail);
              detailDialog.close();
            "
          >
            <ShoppingBag :size="17" />
            В корзину
          </button>
          <p class="mt-5 flex items-center gap-2 text-xs text-muted">
            <Truck :size="15" />
            Оплата при получении
          </p>
        </div>
      </div>
    </dialog>
    <div
      class="fixed bottom-6 right-5 z-[100] flex max-w-[min(360px,90vw)] flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      <TransitionGroup name="fade">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="flex items-center gap-3 rounded-xl px-5 py-4 text-sm text-white shadow-xl"
          :class="toast.error ? 'bg-red-800' : 'bg-ink'"
        >
          <component :is="toast.error ? X : Check" :size="17" class="shrink-0" />
          {{ toast.text }}
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>
