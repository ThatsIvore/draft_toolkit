import subprocess


def test_priority_group_renders_once_and_filter_keeps_fallback_accessible():
    subprocess.run(["node", "-e", r"""
const vm = require('vm'), fs = require('fs'), assert = require('assert');
const p = (id, action, lead = 1) => ({player_id:id,player:'Player '+id,
  replacement:{action,drop_player:'Collins',lead_player_id:lead,combined_delta:30-id},intelligence:{}});
const context = {DATA:{available_players:[p(1,'PRIORITY MOVE'),p(2,'ALTERNATIVE'),p(3,'CONSIDER')]},
 SORT:'swap',esc:String,filtered:x=>x,playerCard:p=>`<article>${p.player}</article>`,
 openPlayer:()=>{},allPlayers:()=>[],recommendationClass:x=>x};
vm.createContext(context);vm.runInContext(fs.readFileSync('public/waiver-v4.js','utf8'),context);
let html=context.renderAvailable();
assert.equal((html.match(/<article>Player 1/g)||[]).length,1);
assert.equal((html.match(/<article>Player 2/g)||[]).length,1);
assert(html.includes('<details>'));assert(html.includes('1 alternative targets'));
context.filtered=x=>x.filter(p=>p.player_id===2);
html=context.renderAvailable();assert(html.includes('Player 2'));
context.DATA.available_players=[p(3,'CONSIDER')];context.filtered=x=>x;
assert(context.renderAvailable().includes('No priority move clears the checks'));
context.SORT='name';assert(context.renderAvailable().includes('Player 3'));
"""], check=True)
