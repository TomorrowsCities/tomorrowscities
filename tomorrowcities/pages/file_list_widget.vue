<template>
  <v-sheet class="solara-file-list" ref="scrollpane"
      @click="clicked = null"
  >
    <v-list
      @click="clicked = null"
    >
      <v-list-item
          v-for="{name, is_file, size} in files"
          :key="name + '|' + is_file"
          @click.stop="clicked = { name, is_file }"
          @dblclick="double_clicked = { name, is_file }"
          :class="(selected_files.includes(name) || (clicked && clicked.name == name)) ? 'solara-file-list-selected': ''"
          :draggable="is_file && multi_select && !busy"
          @dragstart="startCloudDrag($event, name, is_file)"
      >
        <div v-if="is_file && multi_select" class="tc-cloud-file-checkbox" @click.stop @dblclick.stop>
          <v-checkbox v-model="selected_files" :value="name" :disabled="busy" dense hide-details
                      :aria-label="'Select ' + name" />
        </div>
        <v-list-item-icon>
          <v-icon>{{ name === '..' ? 'mdi-keyboard-backspace' : is_file ? 'mdi-file-document' : 'mdi-folder' }}</v-icon>
        </v-list-item-icon>

        <v-list-item-content>
          <v-list-item-title :class="'solara-file-list-' + (is_file ? 'file' : 'dir')">
            {{ name === '..' ? 'Back to previous folder' : name }}<span v-if="size"> - {{ size }}</span>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-list>
  </v-sheet>
</template>

<script>
module.exports = {
  methods: {
    startCloudDrag(event, name, isFile) {
      if (!isFile || !this.multi_select || this.busy) {
        event.preventDefault();
        return;
      }
      const available = this.files.filter(file => file.is_file).map(file => file.name);
      const names = this.selected_files.includes(name)
        ? available.filter(file => this.selected_files.includes(file)) : [name];
      if (!names.length) { event.preventDefault(); return; }
      if (!this.selected_files.includes(name)) this.selected_files = [name];
      const paths = names.map(file => this.cloud_directory.replace(/\/$/, '') + '/' + file);
      event.dataTransfer.effectAllowed = 'copy';
      event.dataTransfer.setData('application/x-tcdse-cloud-files+json', JSON.stringify({paths}));
      event.dataTransfer.setData('text/plain', names.length + ' cloud file(s)');
    }
  },
  mounted() {
    const element = this.$refs.scrollpane.$el
    element.scrollTop = this.scroll_pos

    this._scrollListener = _.debounce((e) => {
      this.scroll_pos = Math.round(element.scrollTop)
    }, 50)
    element.addEventListener('scroll', this._scrollListener)
  },
  watch: {
    scroll_pos(v) {
      this.$nextTick(() => this.$refs.scrollpane.$el.scrollTop = v);
    }
  }
}
</script>

<style id="solara-file-list">
.solara-file-list {
  overflow: auto;
}

.solara-file-list-dir {
  font-weight: bold;
}

.solara-file-list-selected {
  background-color: #3333;

}

.solara-file-list .v-list-item__icon,
.solara-file-list .v-list-item__list {
  margin-top: 0;
  margin-bottom: 0;
}

.v-application--is-ltr .solara-file-list .v-list-item__icon {
  margin-right: 8px;
}

.solara-file-list .v-list-item {
  height: 28px;
  min-height: 0;
  padding-left: 0;
}
</style>
