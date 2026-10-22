<template>
  <div ref="dropzone" class="solara-file-drop" @click="triggerFileInput">
    <input type="file" ref="fileInput" :multiple="multiple" style="display: none;" @change="onFileChange" />
    <template v-if="allow_cloud && cloud_drop && cloud_drop.paths">
      <div v-for="path in cloud_drop.paths" :key="path" class="solara-file-drop__filename">
        {{ path.split('/').pop() }}
      </div>
    </template>
    <template v-else-if="file_info && file_info.length > 0">
      <template v-if="multiple">
        <div v-for="file in file_info" class="solara-file-drop__filename">
          {{ file.name }}
        </div>
      </template>
      <template v-else>
        <div class="solara-file-drop__filename">
          {{ file_info[0].name }}
        </div>
      </template>
    </template>
    <template v-else>
      {{ label }}
    </template>
  </div>
</template>

<script>
module.exports = {
  mounted() {
    this.chunk_size = 2 * 1024 * 1024;
    this.$refs.dropzone.addEventListener('dragover', event => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'copy';
      this.$refs.dropzone.classList.add('tc-cloud-drop-active');
    });
    this.$refs.dropzone.addEventListener('dragleave', event => {
      if (!this.$refs.dropzone.contains(event.relatedTarget)) {
        this.$refs.dropzone.classList.remove('tc-cloud-drop-active');
      }
    });

    this.$refs.dropzone.addEventListener('drop', event => {
      event.preventDefault();
      this.$refs.dropzone.classList.remove('tc-cloud-drop-active');
      const raw = event.dataTransfer.getData('application/x-tcdse-cloud-files+json');
      if (raw) {
        if (!this.allow_cloud) return;
        let payload;
        try { payload = JSON.parse(raw); } catch (_) { return; }
        if (!Array.isArray(payload.paths) || !payload.paths.length ||
            !payload.paths.every(path => typeof path === 'string')) return;
        this._cloudDropSerial = (this._cloudDropSerial || 0) + 1;
        this.cloud_drop = {paths: payload.paths, request_id: Date.now() + ':' + this._cloudDropSerial};
        return;
      }
      // Native file objects remain lazy: only their names/sizes cross the widget.
      const items = Array.from(event.dataTransfer.items || []);
      const nativeFiles = items.length ? items.filter(item => {
        if (item.kind !== 'file') return false;
        const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
        return !entry || entry.isFile;
      }).map(item => item.getAsFile()).filter(Boolean) : Array.from(event.dataTransfer.files || []);
      if (!nativeFiles.length) return;
      // Clear file information before processing new files
      this.jupyter_clear();

      this.native_file_info = nativeFiles
      this.file_info = this.native_file_info.map(
        ({name, size}) => ({
          name,
          isFile: true,
          size,
        }));
    });
  },
  methods: {
    triggerFileInput() {
      this.$refs.fileInput.click();
    },
    onFileChange(event) {
      if (!event.target.files || event.target.files.length === 0) return;
      this.jupyter_clear();
      const files = Array.from(event.target.files);
      
      this.native_file_info = files;
      this.file_info = this.native_file_info.map(
        ({name, size}) => ({
          name,
          isFile: true,
          size,
        }));
        
      event.target.value = '';
    },
    jupyter_clear() {
      this.cloud_drop = null;
      this.native_file_info = [];
      this.file_info = [];
    },
    jupyter_read(chunk) {
      const {id, file_index, offset, length} = chunk;
      let to_do = length;
      let sub_offset = offset;

      (async () => {
        while (to_do > 0) {
          console.log(this.chunk_size, to_do);
          const sub_length = Math.min(to_do, this.chunk_size);

          const file = this.native_file_info[file_index];
          const blob = file.slice(sub_offset, sub_offset + sub_length);
          const buff = await blob.arrayBuffer();

          const msg = {id, file_index, offset: sub_offset, length: sub_length}
          this.upload(msg, [buff]);

          to_do -= sub_length
          sub_offset += sub_length
        }
      })();
    }
  }
}
</script>

<style id="solara-file-drop">
.solara-file-drop {
  height: 100px;
  border: 1px dashed gray;
  margin: 8px 0;
  padding: 8px;
  overflow: auto;
  cursor: pointer;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
}
.solara-file-drop:hover {
  background-color: rgba(0, 0, 0, 0.05);
}
.solara-file-drop.tc-cloud-drop-active {
  border-color: #279989;
  background-color: rgba(39, 153, 137, 0.1);
}
.solara-file-drop__filename {
  display: block;
  width: 100%;
  max-width: 100%;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}
</style>
