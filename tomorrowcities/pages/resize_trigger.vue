<template>
    <div ref="root" :data-trigger-key="trigger_key" style="width: 100%;">
        <jupyter-widget
            v-for="(element, index) in children"
            :key="`${trigger_key}-${index}`"
            :widget="element"
        ></jupyter-widget>
    </div>
</template>

<script>
module.exports = {
    methods: {
        emitResize() {
            if (typeof window === "undefined") {
                return;
            }
            window.requestAnimationFrame(() => {
                window.dispatchEvent(new Event("resize"));
            });
        },
        observeContainer() {
            if (typeof window === "undefined" || !window.ResizeObserver || !this.$refs.root) {
                return;
            }
            this._observer = new window.ResizeObserver(() => {
                this.emitResize();
            });
            this._observer.observe(this.$refs.root);
        },
        cleanupObserver() {
            if (this._observer) {
                this._observer.disconnect();
                this._observer = null;
            }
        },
    },
    mounted() {
        this.observeContainer();
        this.emitResize();
    },
    updated() {
        this.$nextTick(() => {
            this.emitResize();
        });
    },
    beforeDestroy() {
        this.cleanupObserver();
    },
};
</script>
