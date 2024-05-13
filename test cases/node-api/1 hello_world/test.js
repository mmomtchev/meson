const addon = require(`./build/${process.argv[2]}`);
const { assert } = require('chai');

assert.strictEqual(addon.HelloWorld(), 'world');
