<script setup>
import { ref, reactive, watch, nextTick } from 'vue';
import { X, Minus, Plus, ShoppingBag, ArrowRight, CheckCircle2, Truck } from '@lucide/vue';
import {
  cart,
  cartLines,
  cartTotal,
  checkoutKey,
  user,
  isCustomer,
  api,
  money,
  imageUrl,
  changeQuantity,
  loadProducts,
} from '../store';
const props = defineProps({ open: Boolean });
const emit = defineEmits(['close', 'login', 'ordered']);
const dialog = ref(null);
const step = ref('cart');
const busy = ref(false);
const error = ref('');
const createdOrder = ref(null);
const wantsCheckout = ref(false);
const form = reactive({ recipient: '', phone: '', address: '', note: '' });
watch(
  () => props.open,
  async (value) => {
    await nextTick();
    if (value) {
      step.value = 'cart';
      error.value = '';
      dialog.value?.showModal();
    } else dialog.value?.close();
  },
);
watch(user, (value) => {
  if (value && wantsCheckout.value && isCustomer.value) {
    step.value = 'checkout';
    form.recipient ||= value.name;
    wantsCheckout.value = false;
  }
});
function checkout() {
  if (!user.value) {
    wantsCheckout.value = true;
    emit('login');
    return;
  }
  if (!isCustomer.value) {
    error.value = 'Оформление заказов доступно в аккаунте покупателя';
    return;
  }
  step.value = 'checkout';
  form.recipient ||= user.value.name;
}
async function submit() {
  busy.value = true;
  error.value = '';
  try {
    if (cartLines.value.length !== cart.value.length)
      throw new Error('Один из товаров недоступен. Обновите корзину');
    createdOrder.value = await api('/api/orders', {
      method: 'POST',
      headers: { 'Idempotency-Key': checkoutKey.value },
      body: JSON.stringify({
        ...form,
        items: cart.value.map((line) => ({ product_id: line.id, quantity: line.quantity })),
      }),
    });
    cart.value = [];
    checkoutKey.value = crypto.randomUUID();
    step.value = 'done';
    loadProducts();
  } catch (err) {
    error.value = err.message;
    await loadProducts();
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <dialog
    ref="dialog"
    class="cart-dialog fixed inset-y-0 left-auto right-0 m-0 h-dvh max-h-dvh w-[min(490px,100vw)] max-w-none border-0 p-0 shadow-2xl backdrop:bg-ink/40"
    aria-labelledby="cart-title"
    @cancel.prevent="emit('close')"
  >
    <div class="flex h-full flex-col">
      <div class="flex items-center justify-between border-b border-stone-100 px-7 py-6">
        <h2 id="cart-title" class="font-display text-2xl">
          {{
            step === 'checkout' ? 'Оформление заказа' : step === 'done' ? 'Спасибо за заказ' : 'Ваша корзина'
          }}
        </h2>
        <button aria-label="Закрыть корзину" @click="emit('close')"><X :size="21" /></button>
      </div>
      <div v-if="step === 'done'" class="flex flex-1 flex-col items-center justify-center px-8 text-center">
        <div class="rounded-full bg-green-50 p-5 text-green-700"><CheckCircle2 :size="40" /></div>
        <h3 class="mt-6 font-display text-3xl">Всё получилось</h3>
        <p class="mt-3 text-muted">
          Заказ №{{ String(createdOrder.id).padStart(6, '0') }} оформлен.
          <br />
          Товары зарезервированы для вас.
        </p>
        <p class="mt-4 text-sm text-muted">Статус сборки и доставки появится в ваших заказах.</p>
        <button
          class="primary mt-7"
          @click="
            emit('ordered');
            emit('close');
          "
        >
          Мои заказы
          <ArrowRight :size="16" />
        </button>
      </div>
      <template v-else-if="step === 'cart'">
        <div v-if="!cart.length" class="flex flex-1 flex-col items-center justify-center px-8 text-center">
          <ShoppingBag :size="46" class="text-stone-300" />
          <h3 class="mt-5 font-display text-2xl">Здесь пока пусто</h3>
          <p class="mt-2 text-sm text-muted">Найдите что-нибудь для вашего дома.</p>
          <button class="primary mt-6" @click="emit('close')">Перейти к покупкам</button>
        </div>
        <div v-else class="flex-1 space-y-6 overflow-y-auto p-7">
          <div v-for="line in cartLines" :key="line.id" class="flex gap-4">
            <img
              :src="imageUrl(line.product.image)"
              :alt="line.product.name"
              class="h-24 w-24 rounded-xl bg-paper object-cover"
            />
            <div class="min-w-0 flex-1">
              <h3 class="text-sm font-semibold">{{ line.product.name }}</h3>
              <p class="mt-1 text-sm text-muted">{{ money(line.product.price) }}</p>
              <div class="mt-3 flex items-center justify-between">
                <div class="flex items-center rounded-lg border border-stone-200">
                  <button
                    class="p-2"
                    :aria-label="`Уменьшить количество: ${line.product.name}`"
                    @click="changeQuantity(line.id, -1)"
                  >
                    <Minus :size="13" />
                  </button>
                  <span class="w-7 text-center text-sm">{{ line.quantity }}</span>
                  <button
                    class="p-2"
                    :aria-label="`Увеличить количество: ${line.product.name}`"
                    @click="changeQuantity(line.id, 1)"
                  >
                    <Plus :size="13" />
                  </button>
                </div>
                <span class="text-sm font-semibold">
                  {{ money(Number(line.product.price) * line.quantity) }}
                </span>
              </div>
            </div>
          </div>
          <p
            v-if="cart.length !== cartLines.length"
            class="rounded-lg bg-amber-50 p-3 text-sm text-amber-800"
          >
            Некоторые товары больше недоступны.
            <button
              class="ml-2 underline"
              @click="cart = cart.filter((x) => cartLines.some((l) => l.id === x.id))"
            >
              Убрать
            </button>
          </p>
        </div>
        <div v-if="cart.length" class="border-t border-stone-100 p-7">
          <p v-if="error" role="alert" class="mb-4 text-sm text-red-700">{{ error }}</p>
          <div class="flex justify-between text-lg font-semibold">
            <span>Итого</span>
            <span>{{ money(cartTotal) }}</span>
          </div>
          <p class="my-3 flex items-center gap-2 text-xs text-muted">
            <Truck :size="15" />
            Доставка без доплаты · Оплата при получении
          </p>
          <button class="primary mt-2 w-full" :disabled="cartLines.length !== cart.length" @click="checkout">
            Оформить заказ
            <ArrowRight :size="16" />
          </button>
        </div>
      </template>
      <form v-else class="flex-1 space-y-5 overflow-y-auto p-7" @submit.prevent="submit">
        <button type="button" class="text-sm text-muted" @click="step = 'cart'">← Вернуться в корзину</button>
        <label>
          Получатель
          <input v-model="form.recipient" autocomplete="name" required minlength="2" maxlength="100" />
        </label>
        <label>
          Телефон
          <input
            v-model="form.phone"
            type="tel"
            autocomplete="tel"
            required
            minlength="10"
            maxlength="30"
            placeholder="+7 999 123-45-67"
          />
        </label>
        <label>
          Адрес доставки
          <textarea
            v-model="form.address"
            autocomplete="street-address"
            required
            minlength="8"
            maxlength="300"
            rows="3"
            placeholder="Город, улица, дом, квартира"
          />
        </label>
        <label>
          Комментарий к заказу
          <textarea v-model="form.note" maxlength="500" rows="2" placeholder="Например, код домофона" />
        </label>
        <div class="rounded-xl bg-paper p-4">
          <p class="font-semibold">Оплата при получении</p>
          <p class="mt-1 text-sm text-muted">Сумма заказа: {{ money(cartTotal) }}. Доставка без доплаты.</p>
        </div>
        <p v-if="error" role="alert" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
        <button class="primary w-full" :disabled="busy">
          {{ busy ? 'Оформляем…' : 'Подтвердить заказ' }}
          <ArrowRight v-if="!busy" :size="16" />
        </button>
      </form>
    </div>
  </dialog>
</template>
