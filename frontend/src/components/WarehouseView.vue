<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { PackageCheck, RefreshCw, ArrowRight, Check } from '@lucide/vue';
import { api, money, timestamp, statusClass, notify, user, isManager, usePolling } from '../store';
const orders = ref([]);
const filter = ref('all');
const busy = ref(null);
const polling = usePolling(async () => {
  orders.value = await api('/api/warehouse/orders');
});
const visible = computed(() =>
  orders.value.filter((o) => filter.value === 'all' || o.status === filter.value),
);
const filters = [
  ['all', 'Все задания'],
  ['queued', 'Ожидают'],
  ['picking', 'В сборке'],
  ['ready', 'Готовы'],
  ['shipped', 'В доставке'],
];
onMounted(polling.start);
onUnmounted(polling.stop);
const canHandle = (order) => !order.assignee_id || order.assignee_id === user.value?.id || isManager.value;
async function action(order, status) {
  busy.value = order.id;
  try {
    await api(`/api/warehouse/orders/${order.id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    });
    await polling.refresh();
    notify('Статус заказа обновлён');
  } catch (err) {
    notify(err.message, true);
  } finally {
    busy.value = null;
  }
}
async function pick(order, item, checked) {
  busy.value = order.id;
  try {
    await api(`/api/warehouse/orders/${order.id}/items/${item.id}`, {
      method: 'POST',
      body: JSON.stringify({ picked: checked ? item.quantity : 0 }),
    });
    await polling.refresh();
  } catch (err) {
    notify(err.message, true);
  } finally {
    busy.value = null;
  }
}
</script>

<template>
  <section class="mx-auto max-w-6xl px-5 py-12 md:px-8">
    <div class="flex items-end justify-between">
      <div>
        <p class="eyebrow text-accent">Рабочий кабинет</p>
        <h1 class="mt-3 font-display text-4xl">Сборка и доставка</h1>
        <p class="mt-3 text-muted">Каждый заказ — ещё один дом, в котором станет уютнее.</p>
      </div>
      <button class="secondary" aria-label="Обновить задания" @click="polling.refresh">
        <RefreshCw :size="17" />
      </button>
    </div>
    <div class="mt-8 flex flex-wrap gap-2">
      <button
        v-for="[value, label] in filters"
        :key="value"
        class="rounded-full border px-4 py-2 text-sm"
        :class="filter === value ? 'border-ink bg-ink text-white' : 'border-stone-200 bg-white text-muted'"
        @click="filter = value"
      >
        {{ label }}
        <span class="ml-2 opacity-60">
          {{ orders.filter((o) => value === 'all' || o.status === value).length }}
        </span>
      </button>
    </div>
    <p v-if="polling.state.error" role="alert" class="mt-6 rounded-xl bg-red-50 p-4 text-red-700">
      {{ polling.state.error }}
    </p>
    <p v-if="polling.state.loading" class="mt-8 text-muted">Загружаем задания…</p>
    <div v-else-if="!visible.length" class="card mt-6 p-12 text-center">
      <PackageCheck :size="42" class="mx-auto text-stone-300" />
      <h2 class="mt-4 font-display text-2xl">Пока нет заданий</h2>
      <p class="mt-2 text-sm text-muted">Новые заказы появятся здесь после обработки.</p>
    </div>
    <div class="mt-6 grid gap-5 md:grid-cols-2">
      <article v-for="order in visible" :key="order.id" class="card p-6">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">Заказ №{{ String(order.id).padStart(6, '0') }}</h2>
          <span class="rounded-full px-3 py-1 text-xs" :class="statusClass(order.status)">
            {{ order.status_label }}
          </span>
        </div>
        <p class="mt-2 text-xs text-muted">{{ timestamp(order.created_at) }} · {{ money(order.total) }}</p>
        <div class="mt-5 rounded-xl bg-paper p-4 text-sm">
          <strong>{{ order.recipient }}</strong>
          <p class="mt-1">{{ order.address }}</p>
          <p class="mt-1 text-muted">{{ order.phone }}</p>
          <p v-if="order.note" class="mt-2 text-muted">{{ order.note }}</p>
        </div>
        <div class="mt-5 space-y-3">
          <label v-for="item in order.items" :key="item.id" class="flex items-center gap-3 font-normal">
            <input
              type="checkbox"
              :checked="item.picked === item.quantity"
              :disabled="order.status !== 'picking' || !canHandle(order) || busy === order.id"
              @change="pick(order, item, $event.target.checked)"
            />
            <span class="flex-1">{{ item.name }}</span>
            <span class="text-muted">{{ item.quantity }} шт.</span>
          </label>
        </div>
        <div class="mt-6">
          <button
            v-if="order.status === 'queued'"
            class="primary w-full"
            :disabled="busy === order.id"
            @click="action(order, 'picking')"
          >
            Взять в сборку
            <ArrowRight :size="16" />
          </button>
          <button
            v-else-if="order.status === 'picking' && canHandle(order)"
            class="primary w-full"
            :disabled="busy === order.id || order.items.some((i) => i.picked !== i.quantity)"
            @click="action(order, 'ready')"
          >
            Заказ собран
            <Check :size="16" />
          </button>
          <button
            v-else-if="order.status === 'ready' && canHandle(order)"
            class="primary w-full"
            :disabled="busy === order.id"
            @click="action(order, 'shipped')"
          >
            Передать на доставку
            <ArrowRight :size="16" />
          </button>
          <button
            v-else-if="order.status === 'shipped' && isManager"
            class="primary w-full"
            :disabled="busy === order.id"
            @click="action(order, 'delivered')"
          >
            Подтвердить доставку
            <Check :size="16" />
          </button>
          <p v-else class="text-sm text-muted">
            {{
              order.status === 'shipped'
                ? 'Ожидает подтверждения доставки менеджером.'
                : 'Заказ собирает другой сотрудник.'
            }}
          </p>
        </div>
      </article>
    </div>
  </section>
</template>
