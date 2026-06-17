<template>
    <div
        style="width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;"
    >
        <svg
            viewBox="0 0 120 72"
            width="120"
            height="72"
            aria-hidden="true"
            style="display: block; margin: 0 auto;"
        >
            <path
                d="M 18 56 A 42 42 0 0 1 102 56"
                fill="none"
                stroke="#c9c9c9"
                stroke-width="8"
                stroke-linecap="round"
            />
            <path
                v-if="progress_length > 0.5"
                d="M 18 56 A 42 42 0 0 1 102 56"
                fill="none"
                stroke="#4d6fd3"
                stroke-width="8"
                stroke-linecap="round"
                :stroke-dasharray="`${progress_length.toFixed(2)} ${semicircle_length.toFixed(2)}`"
            />
        </svg>
        <div
            style="margin-top: -2px; font-size: 18px; font-weight: 700; line-height: 1; color: #4d6fd3; text-align: center;"
        >
            {{ value_text }}
        </div>
    </div>
</template>

<script>
module.exports = {
    props: {
        progress_ratio: {
            type: Number,
            default: 0,
        },
        value_text: {
            type: String,
            default: "0",
        },
    },
    computed: {
        clamped_ratio() {
            return Math.max(0, Math.min(1, this.progress_ratio || 0));
        },
        semicircle_length() {
            return Math.PI * 42;
        },
        progress_length() {
            return this.semicircle_length * this.clamped_ratio;
        },
    },
};
</script>
