import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const { chromium } = createRequire(import.meta.url)('playwright');
const cardPath = fileURLToPath(new URL('../../custom_components/ninebot_connect/frontend/ninebot-vehicle-card.js', import.meta.url));
let browser;

before(async () => { browser = await chromium.launch({ headless: true, channel: process.env.NINEBOT_BROWSER_CHANNEL || undefined }); });
after(async () => { await browser?.close(); });

async function pageWithCard(options = {}, clock = false) {
  const page = await browser.newPage({ viewport: { width: 360, height: 900 } });
  page.setDefaultTimeout(3000);
  if (clock) await page.clock.install({time:new Date('2026-11-24T00:00:00Z')});
  await page.setContent('<style>body{margin:12px;background:#f4f6f5;--primary-text-color:#202825;--secondary-text-color:#63706a;--ha-card-background:#fff;--divider-color:#e4eae6;--primary-color:#28786c;font-family:system-ui}</style>');
  await page.addScriptTag({ path: cardPath });
  await page.evaluate((options) => {
    const state = (role, value, attributes = {}) => ({
      entity_id: `sensor.test_${role}`, state: value,
      attributes: { ninebot_connect_role: role, ...attributes },
    });
    const states = {
      'sensor.test_battery': state('battery', '72', { unit_of_measurement: '%' }),
      'sensor.test_range': state('range', '48.6', { unit_of_measurement: 'km' }),
      'binary_sensor.test_power': state('power_on', 'on'),
      'binary_sensor.test_charging': state('charging', 'off'),
      'sensor.test_reported': state('reported_at', new Date().toISOString()),
    };
    const entities = Object.fromEntries(Object.keys(states).map(id => [id, { device_id: 'test-device', platform: 'ninebot_connect' }]));
    const hass = {
      states, entities, devices: { 'test-device': { id: 'test-device', name: '测试电动车' } },
      locale: { language: 'zh-Hans', number_format: 'comma_decimal' }, language: 'zh-Hans',
      formatEntityState: s => s.state,
    };
    window.testHass = hass;
    const card = document.createElement('ninebot-vehicle-card');
    card.id = 'card';
    card.setConfig({ type: 'custom:ninebot-vehicle-card', device_id: 'test-device', ...options });
    card.hass = hass;
    document.body.append(card);
  }, options);
  return page;
}

test('selecting a device renders battery, precise range and independent power', async () => {
  const page = await pageWithCard();
  try {
    assert.equal(await page.getByRole('heading', { name: '测试电动车' }).count(), 1);
    assert.equal(await page.getByRole('button', { name: '电量：72%' }).count(), 1);
    assert.equal(await page.getByRole('button', { name: '精准预计续航：48.6 km' }).count(), 1);
    assert.equal(await page.getByText('已开机', { exact: true }).count(), 1);
    assert.equal(await page.getByText('未充电', { exact: true }).count(), 1);
  } finally { await page.close(); }
});

test('battery details preserve expansion across state changes and only show supported cycles', async () => {
  const page = await pageWithCard();
  try {
    await page.evaluate(() => {
      const h = window.testHass;
      for (const [role, value, attributes] of [
        ['battery_1_voltage','52.4', {unit_of_measurement:'V'}],
        ['battery_1_temperature','24', {unit_of_measurement:'°C'}],
        ['battery_1_cycles','186', {cycle_count_supported: true}],
        ['battery_1_score','92', {}],
      ]) {
        const id = `sensor.test_${role}`;
        h.states[id] = {entity_id:id,state:value,attributes:{ninebot_connect_role:role,...attributes}};
        h.entities[id] = {device_id:'test-device',platform:'ninebot_connect'};
      }
      document.getElementById('card').hass = {...h};
    });
    await page.getByText('电池详情', {exact:true}).click();
    assert.equal(await page.getByRole('button', {name:'电池槽位1电压：52.4 V'}).isVisible(), true);
    assert.equal(await page.getByRole('button', {name:'电池槽位1循环次数：186 次'}).isVisible(), true);
    await page.evaluate(() => {
      const h = window.testHass;
      h.states['sensor.test_battery'].state = '71';
      h.states['sensor.test_battery_1_cycles'].attributes.cycle_count_supported = false;
      document.getElementById('card').hass = {...h};
    });
    assert.equal(await page.getByRole('button', {name:'电量：71%'}).count(), 1);
    assert.equal(await page.getByRole('button', {name:'电池槽位1电压：52.4 V'}).isVisible(), true);
    assert.equal(await page.getByRole('button', {name:/电池槽位1循环次数/}).count(), 0);
    assert.equal(await page.getByText('接口评分 · 非 SOH', {exact:true}).count(), 1);
    await page.evaluate(() => {
      window.testHass.states['sensor.test_battery_1_voltage'].state = 'unavailable';
      document.getElementById('card').hass = {...window.testHass};
    });
    assert.equal(await page.getByText('电压 · 不可用',{exact:true}).count(),1);
  } finally { await page.close(); }
});

test('metric clicks request HA more-info without calling services or external APIs', async () => {
  const page = await pageWithCard();
  try {
    await page.evaluate(() => {
      window.moreInfo = [];
      document.addEventListener('hass-more-info', event => window.moreInfo.push(event.detail));
      window.testHass.callService = () => { throw new Error('Unexpected service call'); };
    });
    await page.getByRole('button', {name:'电量：72%'}).click();
    assert.deepEqual(await page.evaluate(() => window.moreInfo), [{entityId:'sensor.test_battery'}]);
  } finally { await page.close(); }
});

test('visual editor selects only Ninebot devices and emits complete configuration', async () => {
  const page = await pageWithCard();
  try {
    await page.evaluate(() => {
      const Card = customElements.get('ninebot-vehicle-card');
      const editor = Card.getConfigElement();
      editor.setConfig({type:'custom:ninebot-vehicle-card',device_id:'test-device'});
      editor.hass = window.testHass;
      editor.addEventListener('config-changed', e => window.editedConfig = e.detail.config);
      document.body.append(editor);
    });
    assert.equal(await page.getByLabel('车辆', {exact:true}).inputValue(), 'test-device');
    await page.getByLabel('卡片标题', {exact:true}).fill('我的电动车');
    await page.getByLabel('卡片标题', {exact:true}).press('Tab');
    const config = await page.evaluate(() => window.editedConfig);
    assert.equal(config.device_id, 'test-device');
    assert.equal(config.title, '我的电动车');
    assert.equal(config.type, 'custom:ninebot-vehicle-card');
    assert.equal(await page.evaluate(() => window.customCards.some(c => c.type === 'ninebot-vehicle-card')), true);
  } finally { await page.close(); }
});

test('unavailable data and old reports remain distinct from independent power state', async () => {
  const page = await pageWithCard();
  try {
    await page.evaluate(() => {
      const h = window.testHass;
      h.states['sensor.test_battery'].state = 'unavailable';
      h.states['sensor.test_range'].state = 'unknown';
      h.states['sensor.test_reported'].state = new Date(Date.now()-45*60000).toISOString();
      document.getElementById('card').hass = {...h};
    });
    assert.equal(await page.getByRole('button', {name:'电量：—%'}).count(),1);
    assert.equal(await page.getByText('已开机',{exact:true}).count(),1);
    assert.equal(await page.getByText(/车况上报较旧/).count(),1);
    assert.match(await page.getByRole('status').textContent(), /电量不可用/);
  } finally { await page.close(); }
});

test('device bindings do not cross vehicles and dynamic strings cannot become markup', async () => {
  const page = await pageWithCard();
  try {
    await page.evaluate(() => {
      const h = window.testHass;
      h.states['sensor.other_battery'] = {state:'9',attributes:{ninebot_connect_role:'battery'}};
      h.entities['sensor.other_battery'] = {device_id:'another-device',platform:'ninebot_connect'};
      h.devices['another-device'] = {name:'另一辆车'};
      document.getElementById('card').hass = {...h};
      document.getElementById('card').setConfig({device_id:'test-device',title:'<img src=x onerror="window.INJECTED=true">'});
    });
    assert.equal(await page.getByRole('button',{name:'电量：72%'}).count(),1);
    assert.equal(await page.getByRole('heading',{name:'<img src=x onerror="window.INJECTED=true">'}).count(),1);
    assert.equal(await page.locator('ninebot-vehicle-card img').count(),0);
    assert.equal(await page.evaluate(() => window.INJECTED),undefined);
    await page.evaluate(() => document.getElementById('card').setConfig({device_id:'another-device'}));
    assert.equal(await page.getByRole('button',{name:'电量：9%'}).count(),1);
  } finally { await page.close(); }
});

test('timestamps advance without vehicle changes and stop updating after disconnect', async () => {
  const page = await pageWithCard({},true);
  try {
    await page.clock.fastForward(120000);
    assert.equal(await page.getByText('车况上报 2分钟前',{exact:true}).count(),1);
    const before = await page.evaluate(() => {
      window.detachedCard = document.getElementById('card');
      window.detachedCard.remove();
      return window.detachedCard.shadowRoot.textContent;
    });
    await page.clock.fastForward(600000);
    assert.equal(await page.evaluate(() => window.detachedCard.shadowRoot.textContent),before);
    await page.evaluate(() => document.body.append(window.detachedCard));
    assert.equal(await page.getByText('车况上报 12分钟前',{exact:true}).count(),1);
  } finally { await page.close(); }
});

test('320px, light and dark layouts fit and details grow naturally', async () => {
  const page = await pageWithCard();
  try {
    await page.setViewportSize({width:320,height:950});
    const before = await page.locator('#card').boundingBox();
    await page.getByText('电池详情',{exact:true}).click();
    const after = await page.locator('#card').boundingBox();
    assert.ok(after.height > before.height);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    await page.evaluate(() => document.body.style.setProperty('--ha-card-background','#202322'));
    assert.equal(await page.locator('ha-card').evaluate(el => getComputedStyle(el).backgroundColor),'rgb(32, 35, 34)');
  } finally { await page.close(); }
});

test('masonry receives a useful height estimate before the card is mounted', async () => {
  const page = await pageWithCard();
  try {
    assert.equal(await page.evaluate(() => document.createElement('ninebot-vehicle-card').getCardSize()),6);
  } finally { await page.close(); }
});
