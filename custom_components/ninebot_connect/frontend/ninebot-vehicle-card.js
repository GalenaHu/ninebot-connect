/* Ninebot Connect · MIT · local-only dashboard card, no runtime dependencies. */
(() => {
  'use strict';

  const TYPE = 'ninebot-vehicle-card';
  const ROLE = 'ninebot_connect_role';
  const VALID_ROLE = /^(battery|range|power_on|charging|reported_at|location|location_at|mileage|charging_power|backup_battery|battery_details_at|battery_[1-8]_(voltage|temperature|electricity|cycles|score))$/;
  const UNKNOWN = new Set(['unknown', 'unavailable', '']);

  function configOf(config) {
    if (!config || typeof config !== 'object' || Array.isArray(config)) throw new Error('卡片配置无效');
    if (config.device_id !== undefined && (typeof config.device_id !== 'string' || config.device_id.length > 128)) throw new Error('请选择有效的车辆设备');
    if (config.title !== undefined && (typeof config.title !== 'string' || config.title.length > 160)) throw new Error('标题不能超过160个字符');
    for (const key of ['show_location', 'show_details']) {
      if (config[key] !== undefined && typeof config[key] !== 'boolean') throw new Error(`${key} 必须是布尔值`);
    }
    const entities = Object.create(null);
    if (config.entities !== undefined) {
      if (!config.entities || typeof config.entities !== 'object' || Array.isArray(config.entities)) throw new Error('entities 必须是角色与实体ID的映射');
      for (const [role, entity] of Object.entries(config.entities)) {
        if (!VALID_ROLE.test(role) || typeof entity !== 'string' || !/^[a-z_]+\.[a-z0-9_]+$/.test(entity)) throw new Error('实体角色或实体ID无效');
        entities[role] = entity;
      }
    }
    return { ...config, entities, show_location: config.show_location !== false, show_details: config.show_details !== false };
  }

  function bindings(hass, config) {
    const result = Object.create(null);
    if (config.device_id) {
      for (const [id, state] of Object.entries(hass?.states || {})) {
        const entry = hass.entities?.[id];
        const role = state.attributes?.[ROLE];
        if (entry?.device_id === config.device_id && entry.platform === 'ninebot_connect' && VALID_ROLE.test(role || '')) {
          // Never choose arbitrarily between duplicate roles.
          result[role] = Object.hasOwn(result, role) ? null : id;
        }
      }
    }
    return Object.assign(result, config.entities);
  }

  function vehicles(hass) {
    const ids = new Set();
    for (const [id,state] of Object.entries(hass?.states || {})) {
      const entry = hass.entities?.[id];
      if (entry?.device_id && entry.platform === 'ninebot_connect' && VALID_ROLE.test(state.attributes?.[ROLE] || '')) ids.add(entry.device_id);
    }
    return [...ids].sort().map(id => ({id,name:hass.devices?.[id]?.name_by_user || hass.devices?.[id]?.name || '九号电动车'}));
  }

  function measurement(hass, state, fallbackUnit, min = 0, max = Infinity) {
    const raw = state?.state;
    const unit = state?.attributes?.unit_of_measurement || fallbackUnit;
    const numeric = typeof raw === 'string' && raw.trim() && !UNKNOWN.has(raw) ? Number(raw) : NaN;
    if (!Number.isFinite(numeric) || numeric < min || numeric > max) return { text: '—', unit, value: null, status:raw === 'unavailable' ? '不可用' : '未知' };
    let text;
    if (hass.formatEntityState) {
      text = String(hass.formatEntityState(state));
      if (unit && text.endsWith(unit)) text = text.slice(0, -unit.length).trim();
    } else {
      text = new Intl.NumberFormat(hass.locale?.language || hass.language || 'zh-CN', { maximumFractionDigits: 2 }).format(numeric);
    }
    return { text, unit, value: numeric };
  }

  const STYLE = `
    :host { display:block; min-width:0; container-type:inline-size; --nb-accent:var(--primary-color,#28786c); --nb-muted:var(--secondary-text-color,#63706a); --nb-line:var(--divider-color,#e4eae6); }
    * { box-sizing:border-box; }
    ha-card { display:block; padding:23px; border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color,var(--nb-line)); border-radius:var(--ha-card-border-radius,22px); background:var(--ha-card-background,var(--card-background-color,#fff)); color:var(--primary-text-color,#202825); font-family:var(--ha-font-family-body,Roboto,system-ui,sans-serif); line-height:1.45; overflow-wrap:anywhere; }
    h2,p { margin:0; }
    .header { display:flex; justify-content:space-between; align-items:center; gap:12px; }
    h2 { font-size:16px; font-weight:500; min-width:0; }
    .badge { display:inline-flex; align-items:center; gap:6px; flex:none; border-radius:999px; padding:5px 9px; font-size:12px; color:var(--nb-accent); background:color-mix(in srgb,var(--nb-accent) 11%,transparent); }
    .dot { width:5px; height:5px; border-radius:50%; background:currentColor; }
    .metrics { display:grid; grid-template-columns:1fr 1.12fr; gap:14px; align-items:end; margin-top:29px; }
    button { font:inherit; color:inherit; }
    .metric { display:block; width:100%; min-width:0; border:0; padding:0; background:none; text-align:start; cursor:pointer; }
    .label { display:block; color:var(--nb-muted); font-size:12px; margin-bottom:4px; }
    .value { font-variant-numeric:tabular-nums; letter-spacing:-1px; line-height:1.15; }
    .battery-value { font-size:66px; font-weight:400; letter-spacing:-3px; }
    .unit { color:var(--nb-muted); font-size:14px; font-weight:400; letter-spacing:0; }
    .battery-unit { font-size:23px; margin-inline-start:3px; }
    .range-value { font-size:29px; font-weight:500; }
    .charging { color:var(--nb-muted); font-size:12px; margin-top:5px; }
    .meter { height:5px; border-radius:8px; overflow:hidden; background:var(--nb-line); margin-top:17px; }
    .meter-fill { display:block; height:100%; border-radius:inherit; background:var(--nb-accent); width:0; }
    .message { color:var(--nb-muted); font-size:13px; margin-top:15px; }
    .footer { display:flex; justify-content:space-between; flex-wrap:wrap; gap:7px 12px; margin-top:23px; color:var(--nb-muted); font-size:12px; }
    .location { border:0; background:none; padding:0; min-height:32px; cursor:pointer; text-align:start; }
    .report { align-self:center; }
    .location-time,.detail-time { color:var(--nb-muted); font-size:11px; margin-top:6px; }
    details { margin-top:19px; border-top:1px solid var(--nb-line); }
    summary { min-height:47px; display:flex; align-items:center; justify-content:space-between; gap:12px; font-size:13px; cursor:pointer; list-style:none; }
    summary::-webkit-details-marker { display:none; }
    summary::after { content:'⌄'; color:var(--nb-muted); font-size:17px; }
    details[open] summary::after { content:'⌃'; }
    .detail-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:17px 16px; padding:3px 0 14px; }
    .detail-grid .value { font-size:18px; letter-spacing:0; }
    .slot-name { margin:8px 0 13px; color:var(--nb-muted); font-size:12px; font-weight:400; }
    .detail-empty { color:var(--nb-muted); font-size:12px; padding-bottom:12px; }
    .unavailable { color:var(--nb-muted); }
    .badge.unavailable { color:var(--nb-muted); background:color-mix(in srgb,var(--nb-muted) 10%,transparent); }
    button:focus-visible,summary:focus-visible { outline:2px solid var(--nb-accent); outline-offset:4px; border-radius:3px; }
    @media (pointer:coarse) { .metric,.location { min-height:44px; } }
    [hidden] { display:none!important; }
    @container (max-width:330px) { ha-card {padding:18px} .battery-value {font-size:56px} .range-value {font-size:25px} .metrics {gap:10px} }
  `;

  class NinebotVehicleCard extends HTMLElement {
    static getConfigElement() { return document.createElement(`${TYPE}-editor`); }
    static getStubConfig(hass) {
      const device = vehicles(hass)[0];
      return device ? {device_id:device.id} : {};
    }
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>
        <header class="header"><h2></h2><span class="badge"><span class="dot" aria-hidden="true"></span><span data-power></span></span></header>
        <div class="metrics">
          <button type="button" class="metric" data-role="battery"><span class="label">当前电量</span><span class="value battery-value" data-battery></span><span class="unit battery-unit">%</span></button>
          <div><button type="button" class="metric" data-role="range"><span class="label">精准预计续航</span><span class="value range-value" data-range></span> <span class="unit" data-range-unit></span></button><p class="charging"></p></div>
        </div>
        <div class="meter" role="meter" aria-label="电量" aria-valuemin="0" aria-valuemax="100"><span class="meter-fill"></span></div>
        <p class="message" role="status" hidden></p>
        <div class="footer"><button class="location" data-role="location" type="button"></button><p class="report"></p></div>
        <p class="location-time"></p>
        <details><summary>电池详情</summary><div class="detail-content"></div><p class="detail-time"></p></details>
      </ha-card>`;
      this._detailRows = new Map();
      this._detailGroups = new Map();
      this.shadowRoot.addEventListener('click', event => {
        const button = event.target instanceof Element ? event.target.closest('button[data-role]') : null;
        const entityId = this._bindings?.[button?.dataset.role];
        if (entityId) this.dispatchEvent(new CustomEvent('hass-more-info', {detail:{entityId},bubbles:true,composed:true}));
      });
    }

    setConfig(config) { this._config = configOf(config); this._render(); }
    set hass(hass) { this._hass = hass; this._render(); }
    connectedCallback() {
      this._renderTimes();
      if (!this._timer) this._timer = setInterval(() => this._renderTimes(),60000);
    }
    disconnectedCallback() { clearInterval(this._timer); this._timer = undefined; }
    getCardSize() { const height = this.getBoundingClientRect().height; return height > 0 ? Math.max(1,Math.ceil(height/50)) : 6; }
    getGridOptions() { return { columns: 12, rows: 'auto', min_columns: 6 }; }

    _render() {
      if (!this._config || !this._hass) return;
      const hass = this._hass;
      this._bindings = bindings(hass, this._config);
      const state = role => hass.states[this._bindings[role]];
      const root = this.shadowRoot;
      root.querySelector('h2').textContent = this._config.title || hass.devices?.[this._config.device_id]?.name_by_user || hass.devices?.[this._config.device_id]?.name || '九号电动车';
      const battery = measurement(hass, state('battery'), '%', 0, 100);
      const range = measurement(hass, state('range'), 'km');
      root.querySelector('[data-battery]').textContent = battery.text;
      root.querySelector('[data-range]').textContent = range.text;
      root.querySelector('[data-range-unit]').textContent = range.unit;
      root.querySelector('[data-role=battery]').setAttribute('aria-label', `电量：${battery.text}%`);
      root.querySelector('[data-role=range]').setAttribute('aria-label', `精准预计续航：${range.text} ${range.unit}`);
      const power = state('power_on')?.state;
      root.querySelector('[data-power]').textContent = power === 'on' ? '已开机' : power === 'off' ? '已关机' : power === 'unavailable' ? '开机状态不可用' : '开机状态未知';
      root.querySelector('.badge').classList.toggle('unavailable',power !== 'on');
      const charging = state('charging')?.state;
      root.querySelector('.charging').textContent = charging === 'on' ? '充电中' : charging === 'off' ? '未充电' : charging === 'unavailable' ? '充电状态不可用' : '充电状态未知';
      root.querySelector('.meter-fill').style.width = `${battery.value ?? 0}%`;
      const meter = root.querySelector('.meter');
      if (battery.value === null) { meter.removeAttribute('aria-valuenow'); meter.setAttribute('aria-valuetext', '电量未知'); }
      else { meter.setAttribute('aria-valuenow', String(battery.value)); meter.setAttribute('aria-valuetext', `${battery.text}%`); }
      const message = root.querySelector('.message');
      const notices = [[battery,'battery','电量'],[range,'range','续航']].filter(([value]) => value.value === null).map(([,role,label]) => `${label}${state(role)?.state === 'unavailable' ? '不可用' : '未知'}`);
      message.textContent = !this._bindings.battery ? (this._config.device_id ? '未找到此车辆的电量实体，请确认集成已更新或手动绑定实体。' : '请选择九号车辆。') : notices.join(' · ');
      message.hidden = !message.textContent;
      root.querySelector('details').hidden = !this._config.show_details;
      this._renderDetails();
      this._renderTimes();
    }

    _renderDetails() {
      const root = this.shadowRoot.querySelector('.detail-content');
      const groups = [];
      const slots = new Set(Object.keys(this._bindings).map(role => /^battery_([1-8])_/.exec(role)?.[1]).filter(Boolean));
      const fields = [
        ['voltage','电压','V',0,300], ['temperature','温度','°C',-Infinity,Infinity],
        ['electricity','电量','%',0,100], ['cycles','循环次数','次',0,100000],
        ['score','接口评分 · 非 SOH','',0,100],
      ];
      for (const slot of [...slots].sort()) {
        const rows = [];
        for (const [field,label,unit,min,max] of fields) {
          const role = `battery_${slot}_${field}`;
          const id = this._bindings[role];
          const state = this._hass.states[id];
          if (!id || (field === 'cycles' && state?.attributes?.cycle_count_supported !== true)) continue;
          rows.push(this._detailRow(role, label, `电池槽位${slot}${field === 'score' ? '评分' : label}`, measurement(this._hass,state,unit,min,max)));
        }
        if (rows.length) groups.push(this._detailGroup(`slot_${slot}`, `电池槽位 ${slot}`, rows));
      }
      const extra = [];
      for (const [role,label,unit,max] of [
        ['charging_power','充电功率','W',100000], ['backup_battery','通信备用电池电量','%',100],
        ['mileage','累计里程','km',Infinity],
      ]) {
        if (this._bindings[role]) extra.push(this._detailRow(role,label,label,measurement(this._hass,this._hass.states[this._bindings[role]],unit,0,max)));
      }
      if (extra.length) groups.push(this._detailGroup('extra','',extra));
      if (!groups.length) {
        if (!this._emptyDetails) { this._emptyDetails = document.createElement('p'); this._emptyDetails.className = 'detail-empty'; this._emptyDetails.textContent = '暂未提供电池详情，可确认集成选项中的“读取电池详情”是否开启。'; }
        groups.push(this._emptyDetails);
      }
      this._setChildren(root, groups);
    }

    _detailRow(role, label, accessibleLabel, value) {
      let node = this._detailRows.get(role);
      if (!node) {
        node = document.createElement('button'); node.type = 'button'; node.className = 'metric'; node.dataset.role = role;
        const caption = document.createElement('span'); caption.className = 'label';
        const number = document.createElement('span'); number.className = 'value';
        const unit = document.createElement('span'); unit.className = 'unit';
        node.append(caption, number, document.createTextNode(' '), unit);
        this._detailRows.set(role,node);
      }
      node.querySelector('.label').textContent = label + (value.status ? ` · ${value.status}` : '');
      node.querySelector('.value').textContent = value.text;
      node.querySelector('.unit').textContent = value.unit;
      node.setAttribute('aria-label', `${accessibleLabel}：${value.status || value.text}${value.unit ? ' ' + value.unit : ''}`);
      return node;
    }

    _detailGroup(key, label, rows) {
      let node = this._detailGroups.get(key);
      if (!node) {
        node = document.createElement('section');
        const heading = document.createElement('h3'); heading.className = 'slot-name';
        const grid = document.createElement('div'); grid.className = 'detail-grid';
        node.append(heading,grid); this._detailGroups.set(key,node);
      }
      node.querySelector('h3').textContent = label;
      node.querySelector('h3').hidden = !label;
      this._setChildren(node.querySelector('.detail-grid'),rows);
      return node;
    }

    _setChildren(parent, children) {
      if (parent.childNodes.length !== children.length || [...parent.childNodes].some((node,index) => node !== children[index])) parent.replaceChildren(...children);
    }

    _relative(role, label) {
      const raw = this._hass.states[this._bindings[role]]?.state;
      const time = raw && !UNKNOWN.has(raw) ? Date.parse(raw) : NaN;
      if (!Number.isFinite(time)) return `${label}时间未知`;
      const seconds = Math.floor((Date.now() - time) / 1000);
      if (seconds < -60) return `${label}时间异常`;
      let relative = '刚刚';
      if (seconds >= 60) {
        const [size,unit] = seconds >= 86400 ? [86400,'day'] : seconds >= 3600 ? [3600,'hour'] : [60,'minute'];
        relative = new Intl.RelativeTimeFormat(this._hass.locale?.language || this._hass.language || 'zh-CN', { numeric: 'auto' }).format(-Math.floor(seconds/size),unit);
      }
      return `${label}${role === 'reported_at' && seconds > 900 ? '较旧 ·' : ''} ${relative}`;
    }

    _renderTimes() {
      if (!this._hass || !this._config) return;
      const root = this.shadowRoot;
      root.querySelector('.report').textContent = this._relative('reported_at','车况上报');
      const location = root.querySelector('.location');
      const showLocation = this._config.show_location && Boolean(this._bindings.location);
      location.hidden = !showLocation;
      const place = this._hass.states[this._bindings.location]?.state;
      location.textContent = place === 'home' ? '家中' : place === 'not_home' ? '离家' : place === 'unavailable' ? '位置不可用' : !place || place === 'unknown' ? '位置未知' : place;
      const locationTime = root.querySelector('.location-time');
      locationTime.hidden = !showLocation;
      locationTime.textContent = this._relative('location_at','定位上报');
      const detailTime = root.querySelector('.detail-time');
      detailTime.hidden = !this._bindings.battery_details_at;
      detailTime.textContent = this._relative('battery_details_at','电池查询');
    }
  }

  class NinebotVehicleCardEditor extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({mode:'open'});
      this.shadowRoot.innerHTML = `<style>
        :host {display:block;font-family:var(--ha-font-family-body,Roboto,system-ui,sans-serif);color:var(--primary-text-color);}
        label {display:block;margin-bottom:18px;font-size:14px;}
        select,input[type=text] {display:block;width:100%;box-sizing:border-box;min-height:44px;margin-top:6px;padding:10px 12px;border:1px solid var(--divider-color,#aab5ad);border-radius:8px;color:var(--primary-text-color);background:var(--card-background-color,#fff);font:inherit;}
        .toggle {display:flex;gap:10px;align-items:center;min-height:44px;}
        input[type=checkbox] {width:18px;height:18px;accent-color:var(--primary-color);}
        p {color:var(--secondary-text-color);font-size:12px;line-height:1.6;}
      </style>
      <label>车辆<select aria-label="车辆"></select></label>
      <label>卡片标题<input type="text" maxlength="160" aria-label="卡片标题" placeholder="默认使用车辆名称"></label>
      <label class="toggle"><input type="checkbox" name="show_location">展示位置</label>
      <label class="toggle"><input type="checkbox" name="show_details">展示可折叠的电池详情</label>
      <p>仅使用九号车联现有实体。实体名称可以修改，卡片按设备和角色识别。</p>`;
      this.shadowRoot.addEventListener('change', event => {
        if (!this._config) return;
        const input = event.target;
        const config = {...this._config};
        if (input instanceof HTMLSelectElement) {
          config.device_id = input.value;
          delete config.entities;
        } else if (input.type === 'checkbox') config[input.name] = input.checked;
        else config.title = input.value;
        this._config = config;
        this.dispatchEvent(new CustomEvent('config-changed', {detail:{config},bubbles:true,composed:true}));
      });
    }
    setConfig(config) { configOf(config); this._config = {...config}; this._render(); }
    set hass(hass) { this._hass = hass; this._render(); }
    _render() {
      if (!this._config) return;
      const select = this.shadowRoot.querySelector('select');
      const devices = vehicles(this._hass);
      const signature = JSON.stringify([devices,this._config.device_id]);
      if (signature !== this._devicesSignature) {
        const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = '请选择九号车辆';
        const options = devices.map(device => { const option = document.createElement('option'); option.value = device.id; option.textContent = device.name; return option; });
        if (this._config.device_id && !devices.some(device => device.id === this._config.device_id)) {
          const selected = document.createElement('option'); selected.value = this._config.device_id; selected.textContent = '当前设备（暂未加载）'; options.push(selected);
        }
        select.replaceChildren(placeholder,...options); this._devicesSignature = signature;
      }
      select.value = this._config.device_id || '';
      const title = this.shadowRoot.querySelector('input[type=text]');
      if (this.shadowRoot.activeElement !== title) title.value = this._config.title || '';
      for (const input of this.shadowRoot.querySelectorAll('input[type=checkbox]')) input.checked = this._config[input.name] !== false;
    }
  }

  if (!customElements.get(`${TYPE}-editor`)) customElements.define(`${TYPE}-editor`,NinebotVehicleCardEditor);
  if (!customElements.get(TYPE)) customElements.define(TYPE, NinebotVehicleCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some(card => card.type === TYPE)) window.customCards.push({type:TYPE,name:'九号车联 · 续航便签',description:'电量、精准续航与可折叠电池详情',preview:true,documentationURL:'https://github.com/GalenaHu/ninebot-connect#续航便签卡片'});
})();
