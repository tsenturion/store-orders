<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { Plus, Pencil, X, Download, ArrowUpRight, Package, Coins, Truck, AlertCircle } from '@lucide/vue';
import { api, money, imageUrl, timestamp, notify, download, loadProducts, usePolling } from '../store';
const catalog = ref([]);
const movements = ref([]);
const dashboard = ref({ counts: {}, revenue: 0, sales: [], low_stock: [] });
const tab = ref('products');
const query = ref('');
const dialog = ref(null);
const editId = ref(null);
const reserved = ref(0);
const busy = ref(false);
const error = ref('');
const dates = reactive({ from: '', to: '' });
const form = reactive({
  sku: '',
  name: '',
  description: '',
  category: '',
  image: 'vase',
  price: '',
  stock: 0,
  active: true,
});
const filtered = computed(() =>
  catalog.value.filter((p) => `${p.name} ${p.sku}`.toLowerCase().includes(query.value.toLowerCase())),
);
const activeOrders = computed(() =>
  Object.entries(dashboard.value.counts)
    .filter(([status]) => !['cancelled', 'delivered'].includes(status))
    .reduce((n, [, count]) => n + count, 0),
);
const sales = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    const day = new Date();
    day.setUTCDate(day.getUTCDate() - 6 + i);
    const key = day.toISOString().slice(0, 10);
    return {
      key,
      label: day.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', timeZone: 'UTC' }),
      total: Number(dashboard.value.sales.find((x) => x.day === key)?.total || 0),
    };
  }),
);
const maxSale = computed(() => Math.max(1, ...sales.value.map((x) => x.total)));
const polling = usePolling(async () => {
  const [p, d, m] = await Promise.all([
    api('/api/manager/products'),
    api('/api/manager/dashboard'),
    api('/api/manager/stock-movements'),
  ]);
  catalog.value = p;
  dashboard.value = d;
  movements.value = m;
}, 10000);
onMounted(polling.start);
onUnmounted(polling.stop);
async function edit(product) {
  editId.value = product?.id || null;
  reserved.value = product?.reserved || 0;
  error.value = '';
  Object.assign(
    form,
    product
      ? {
          sku: product.sku,
          name: product.name,
          description: product.description,
          category: product.category,
          image: product.image,
          price: product.price,
          stock: product.stock,
          active: product.active,
        }
      : {
          sku: '',
          name: '',
          description: '',
          category: '',
          image: 'vase',
          price: '',
          stock: 0,
          active: true,
        },
  );
  await nextTick();
  dialog.value.showModal();
}
async function save() {
  busy.value = true;
  error.value = '';
  try {
    await api(`/api/manager/products${editId.value ? '/' + editId.value : ''}`, {
      method: editId.value ? 'PUT' : 'POST',
      body: JSON.stringify({ ...form, stock: Number(form.stock), price: String(form.price) }),
    });
    dialog.value.close();
    notify('Товар сохранён');
    await polling.refresh();
    await loadProducts();
  } catch (err) {
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}
function exportReport() {
  if (dates.from && dates.to && dates.from > dates.to) {
    notify('Проверьте границы периода', true);
    return;
  }
  const params = new URLSearchParams();
  if (dates.from) params.set('date_from', dates.from);
  if (dates.to) params.set('date_to', dates.to);
  download(`/api/manager/reports.xlsx?${params}`, 'polka-sales.xlsx');
}
</script>

<template>
  <section class="mx-auto max-w-7xl px-5 py-12 md:px-8">
    <div class="flex flex-wrap items-end justify-between gap-5">
      <div>
        <p class="eyebrow text-accent">Рабочее пространство</p>
        <h1 class="mt-3 font-display text-4xl">Управление магазином</h1>
        <p class="mt-3 text-muted">Товары, остатки и результаты продаж.</p>
      </div>
      <a class="secondary" href="#warehouse">
        Открыть склад
        <ArrowUpRight :size="16" />
      </a>
    </div>
    <p v-if="polling.state.error" role="alert" class="mt-6 rounded-xl bg-red-50 p-4 text-red-700">
      {{ polling.state.error }}
    </p>
    <div class="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div
        v-for="metric in [
          {
            label: 'Выручка за всё время',
            value: money(dashboard.revenue),
            icon: Coins,
            hint: 'По доставленным заказам',
          },
          { label: 'Заказы в работе', value: activeOrders, icon: Package, hint: 'От оформления до доставки' },
          {
            label: 'Доставлено',
            value: dashboard.counts.delivered || 0,
            icon: Truck,
            hint: 'Завершённые заказы',
          },
          {
            label: 'Товары на исходе',
            value: dashboard.low_stock.length,
            icon: AlertCircle,
            hint: 'Менее 5 доступных единиц',
          },
        ]"
        :key="metric.label"
        class="card p-5"
      >
        <div class="flex items-center justify-between">
          <p class="text-xs text-muted">{{ metric.label }}</p>
          <component :is="metric.icon" :size="18" class="text-accent" />
        </div>
        <p class="mt-4 text-3xl font-semibold tracking-tight">{{ metric.value }}</p>
        <p class="mt-2 text-xs text-muted">{{ metric.hint }}</p>
      </div>
    </div>
    <div class="mt-7 flex gap-6 border-b border-stone-200">
      <button
        v-for="[value, label] in [
          ['products', 'Товары'],
          ['reports', 'Продажи и отчёты'],
          ['movements', 'Движение остатков'],
        ]"
        :key="value"
        class="border-b-2 pb-3 text-sm"
        :class="tab === value ? 'border-ink font-semibold' : 'border-transparent text-muted'"
        @click="tab = value"
      >
        {{ label }}
      </button>
    </div>
    <div v-if="tab === 'products'" class="mt-6">
      <div class="flex flex-wrap justify-between gap-4">
        <input
          v-model="query"
          aria-label="Поиск товара в управлении"
          placeholder="Название или артикул"
          class="max-w-sm"
        />
        <button class="primary" @click="edit(null)">
          <Plus :size="17" />
          Добавить товар
        </button>
      </div>
      <div class="card mt-5 overflow-x-auto">
        <table class="w-full min-w-[760px] text-left text-sm">
          <thead class="bg-paper text-xs text-muted">
            <tr>
              <th class="p-4">Товар</th>
              <th class="p-4">Цена</th>
              <th class="p-4">На складе</th>
              <th class="p-4">Резерв</th>
              <th class="p-4">Доступно</th>
              <th class="p-4">Витрина</th>
              <th class="p-4"><span class="sr-only">Изменить</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in filtered" :key="p.id" class="border-t border-stone-100">
              <td class="p-4">
                <div class="flex items-center gap-3">
                  <img :src="imageUrl(p.image)" alt="" class="h-12 w-12 rounded-lg" />
                  <div>
                    <p class="font-semibold">{{ p.name }}</p>
                    <p class="mt-1 text-xs text-muted">{{ p.sku }} · {{ p.category }}</p>
                  </div>
                </div>
              </td>
              <td class="whitespace-nowrap p-4">{{ money(p.price) }}</td>
              <td class="p-4">{{ p.stock }}</td>
              <td class="p-4">{{ p.reserved }}</td>
              <td class="p-4" :class="p.available < 5 ? 'font-semibold text-accent' : ''">
                {{ p.available }}
              </td>
              <td class="p-4">
                <span
                  :class="p.active ? 'bg-green-50 text-green-700' : 'bg-stone-100 text-stone-500'"
                  class="rounded-full px-2.5 py-1 text-xs"
                >
                  {{ p.active ? 'Активен' : 'Скрыт' }}
                </span>
              </td>
              <td class="p-4">
                <button class="secondary !p-2" :aria-label="`Изменить ${p.name}`" @click="edit(p)">
                  <Pencil :size="15" />
                </button>
              </td>
            </tr>
            <tr v-if="!filtered.length">
              <td colspan="7" class="p-10 text-center text-muted">
                {{ polling.state.loading ? 'Загрузка…' : 'Товары не найдены' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-if="tab === 'reports'" class="mt-6 grid gap-6 lg:grid-cols-3">
      <div class="card p-6 lg:col-span-2">
        <h2 class="font-display text-2xl">Продажи за 7 дней</h2>
        <p class="mt-2 text-xs text-muted">
          Доставленные заказы · дни по UTC · данные обновляются автоматически
        </p>
        <div class="mt-7 flex h-60 items-end gap-3">
          <div
            v-for="day in sales"
            :key="day.key"
            class="flex h-full min-w-0 flex-1 flex-col justify-end text-center"
          >
            <p class="mb-2 text-[11px] text-muted">{{ day.total ? money(day.total) : '—' }}</p>
            <div
              class="mx-auto w-full max-w-14 rounded-t-md bg-ink/85"
              :style="{ height: `${Math.max(2, (day.total / maxSale) * 170)}px` }"
            />
            <p class="mt-3 whitespace-nowrap text-[11px] text-muted">{{ day.label }}</p>
          </div>
        </div>
      </div>
      <form class="card space-y-4 p-6" @submit.prevent="exportReport">
        <h2 class="font-display text-2xl">Отчёт о продажах</h2>
        <p class="text-sm leading-6 text-muted">
          Excel с доставленными заказами, количеством товаров и суммами. Без периода — за всё время.
        </p>
        <label>
          С даты (UTC)
          <input v-model="dates.from" type="date" />
        </label>
        <label>
          По дату (UTC)
          <input v-model="dates.to" type="date" />
        </label>
        <button class="primary w-full">
          <Download :size="16" />
          Скачать Excel
        </button>
      </form>
      <div v-if="dashboard.low_stock.length" class="card p-6 lg:col-span-3">
        <h2 class="font-semibold">Пора пополнить остатки</h2>
        <div class="mt-4 flex flex-wrap gap-3">
          <button v-for="p in dashboard.low_stock" :key="p.id" class="secondary" @click="edit(p)">
            {{ p.name }} · {{ p.available }} шт.
            <Pencil :size="14" />
          </button>
        </div>
      </div>
    </div>
    <div v-if="tab === 'movements'" class="card mt-6 overflow-x-auto">
      <table class="w-full min-w-[670px] text-left text-sm">
        <thead class="bg-paper text-xs text-muted">
          <tr>
            <th class="p-4">Дата</th>
            <th class="p-4">Товар</th>
            <th class="p-4">Изменение</th>
            <th class="p-4">Причина</th>
            <th class="p-4">Сотрудник</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in movements" :key="m.id" class="border-t border-stone-100">
            <td class="p-4 text-xs text-muted">{{ timestamp(m.created_at) }}</td>
            <td class="p-4">{{ m.product }}</td>
            <td class="p-4 font-semibold" :class="m.delta >= 0 ? 'text-green-700' : 'text-accent'">
              {{ m.delta > 0 ? '+' : '' }}{{ m.delta }}
            </td>
            <td class="p-4">{{ m.reason }}</td>
            <td class="p-4 text-muted">{{ m.actor }}</td>
          </tr>
          <tr v-if="!movements.length">
            <td colspan="5" class="p-10 text-center text-muted">Движений пока нет</td>
          </tr>
        </tbody>
      </table>
    </div>
    <dialog
      ref="dialog"
      class="m-auto w-[min(590px,92vw)] rounded-2xl border-0 p-7 shadow-xl backdrop:bg-ink/40"
      aria-labelledby="product-edit-title"
    >
      <div class="flex items-center justify-between">
        <h2 id="product-edit-title" class="font-display text-2xl">
          {{ editId ? 'Изменить товар' : 'Новый товар' }}
        </h2>
        <button aria-label="Закрыть редактор" @click="dialog.close()"><X :size="20" /></button>
      </div>
      <form class="mt-6 space-y-4" @submit.prevent="save">
        <div class="grid grid-cols-2 gap-4">
          <label>
            Артикул
            <input v-model="form.sku" required maxlength="40" pattern="[A-Za-z0-9_-]+" />
          </label>
          <label>
            Категория
            <input v-model="form.category" required maxlength="60" />
          </label>
        </div>
        <label>
          Название
          <input v-model="form.name" required minlength="2" maxlength="120" />
        </label>
        <label>
          Описание
          <textarea v-model="form.description" required minlength="5" maxlength="2000" rows="3" />
        </label>
        <div class="grid grid-cols-2 gap-4">
          <label>
            Цена, ₽
            <input v-model="form.price" type="number" min="0.01" max="10000000" step="0.01" required />
          </label>
          <label>
            Всего на складе
            <input v-model="form.stock" type="number" :min="reserved" max="100000" step="1" required />
          </label>
        </div>
        <p v-if="reserved" class="text-xs text-muted">
          Из общего остатка зарезервировано {{ reserved }} шт. Их нельзя списать вручную.
        </p>
        <label>
          Иллюстрация
          <select v-model="form.image">
            <option
              v-for="[key, label] in [
                ['lamp', 'Лампа'],
                ['vase', 'Ваза'],
                ['chair', 'Стул'],
                ['bottle', 'Графин'],
                ['basket', 'Корзина'],
                ['clock', 'Часы'],
                ['blanket', 'Плед'],
                ['mug', 'Чашка'],
              ]"
              :key="key"
              :value="key"
            >
              {{ label }}
            </option>
          </select>
        </label>
        <label class="flex items-center gap-3">
          <input v-model="form.active" type="checkbox" />
          Показывать на витрине
        </label>
        <p v-if="error" role="alert" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
        <button class="primary w-full" :disabled="busy">{{ busy ? 'Сохраняем…' : 'Сохранить товар' }}</button>
      </form>
    </dialog>
  </section>
</template>
