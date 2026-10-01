<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { Package, Download, ArrowRight, RefreshCw } from '@lucide/vue';
import {
  api,
  money,
  timestamp,
  statusClass,
  notify,
  download,
  loadProducts,
  usePolling,
  user,
} from '../store';
const orders = ref([]);
const expanded = ref(null);
const busy = ref(null);
const polling = usePolling(async () => {
  orders.value = await api('/api/orders');
});
onMounted(polling.start);
onUnmounted(polling.stop);
async function cancel(order) {
  if (!confirm(`Отменить заказ №${order.id}? Резерв товаров будет снят.`)) return;
  busy.value = order.id;
  try {
    await api(`/api/orders/${order.id}/cancel`, { method: 'POST' });
    notify('Заказ отменён');
    await polling.refresh();
    loadProducts();
  } catch (error) {
    notify(error.message, true);
  } finally {
    busy.value = null;
  }
}
</script>

<template>
  <section class="mx-auto max-w-5xl px-5 py-12 md:px-8">
    <div class="flex items-end justify-between gap-4">
      <div>
        <p class="eyebrow text-accent">Личный кабинет</p>
        <h1 class="mt-3 font-display text-4xl">
          {{ user?.role === 'customer' ? 'Мои заказы' : 'Все заказы' }}
        </h1>
        <p class="mt-3 text-muted">От первого выбора до встречи у вашей двери.</p>
      </div>
      <button class="secondary" aria-label="Обновить заказы" @click="polling.refresh">
        <RefreshCw :size="17" />
      </button>
    </div>
    <p v-if="polling.state.error" role="alert" class="mt-6 rounded-xl bg-red-50 p-4 text-red-700">
      {{ polling.state.error }}
    </p>
    <p v-if="polling.state.loading" class="mt-10 text-muted">Загружаем заказы…</p>
    <div v-else-if="!orders.length" class="card mt-8 p-14 text-center">
      <Package :size="44" class="mx-auto text-stone-300" />
      <h2 class="mt-5 font-display text-2xl">Ваш первый заказ впереди</h2>
      <p class="mt-2 text-muted">Выберите вещи, с которыми дома станет уютнее.</p>
      <a href="#catalog" class="primary mt-6">
        Посмотреть каталог
        <ArrowRight :size="16" />
      </a>
    </div>
    <div class="mt-8 space-y-4">
      <article v-for="order in orders" :key="order.id" class="card overflow-hidden">
        <button
          class="flex w-full flex-wrap items-center justify-between gap-4 p-6 text-left"
          :aria-expanded="expanded === order.id"
          @click="expanded = expanded === order.id ? null : order.id"
        >
          <div>
            <span class="font-semibold">Заказ №{{ String(order.id).padStart(6, '0') }}</span>
            <p class="mt-1 text-xs text-muted">
              {{ timestamp(order.created_at) }} · {{ order.items.reduce((n, i) => n + i.quantity, 0) }} шт.
            </p>
          </div>
          <div class="flex items-center gap-5">
            <span :class="statusClass(order.status)" class="rounded-full px-3 py-1.5 text-xs font-medium">
              {{ order.status_label }}
            </span>
            <span class="font-semibold">{{ money(order.total) }}</span>
            <ArrowRight :size="17" class="text-muted" :class="expanded === order.id ? 'rotate-90' : ''" />
          </div>
        </button>
        <div v-if="expanded === order.id" class="border-t border-stone-100 p-6">
          <div class="grid gap-8 md:grid-cols-2">
            <div>
              <h3 class="eyebrow text-muted">Состав заказа</h3>
              <div v-for="item in order.items" :key="item.id" class="mt-4 flex justify-between gap-4 text-sm">
                <span>
                  {{ item.name }}
                  <span class="ml-2 text-muted">× {{ item.quantity }}</span>
                </span>
                <span class="whitespace-nowrap">{{ money(Number(item.price) * item.quantity) }}</span>
              </div>
              <div class="mt-6 rounded-xl bg-paper p-4 text-sm leading-6">
                <strong>{{ order.recipient }}</strong>
                <br />
                {{ order.address }}
                <br />
                <span class="text-muted">{{ order.phone }}</span>
                <p v-if="order.note" class="mt-2 text-muted">{{ order.note }}</p>
              </div>
            </div>
            <div>
              <h3 class="eyebrow text-muted">История заказа</h3>
              <ol class="mt-4 space-y-4">
                <li v-for="(entry, index) in order.history" :key="index" class="flex gap-3 text-sm">
                  <span
                    class="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                    :class="index === order.history.length - 1 ? 'bg-accent' : 'bg-stone-300'"
                  />
                  <div>
                    <p class="font-medium">{{ entry.label }}</p>
                    <p class="mt-1 text-xs text-muted">
                      {{ timestamp(entry.created_at) }} · {{ entry.actor }}
                    </p>
                  </div>
                </li>
              </ol>
              <p v-if="order.status === 'created'" class="mt-5 text-sm text-muted">
                Заказ принят. Готовим задание для склада.
              </p>
            </div>
          </div>
          <div class="mt-6 flex flex-wrap gap-3">
            <button
              v-if="['created', 'queued'].includes(order.status)"
              class="secondary text-red-700"
              :disabled="busy === order.id"
              @click="cancel(order)"
            >
              Отменить заказ
            </button>
            <button
              v-if="order.document_ready"
              class="secondary"
              @click="download(`/api/orders/${order.id}/document.pdf`, `order-${order.id}.pdf`)"
            >
              <Download :size="16" />
              Лист заказа · PDF
            </button>
            <p v-else-if="order.status === 'delivered'" class="text-sm text-muted">
              Готовим PDF с составом заказа…
            </p>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
