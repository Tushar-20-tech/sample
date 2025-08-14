'use strict';
(function(){
	const socket = io();
	let current = { apId: null, playerId: null, highest: 0, highestTeamId: null, end: null };
	const auctionId = window.AUCTION.auctionId;
	const teamId = window.AUCTION.teamId;
	const players = window.AUCTION.players || [];

	const playerInfo = document.getElementById('playerInfo');
	const playerVideo = document.getElementById('playerVideo');
	const currentBid = document.getElementById('currentBid');
	const countdown = document.getElementById('countdown');
	const gavel = document.getElementById('gavel');
	const commentary = document.getElementById('commentary');
	const bidAmount = document.getElementById('bidAmount');
	const placeBidBtn = document.getElementById('placeBidBtn');
	const autoBidMax = document.getElementById('autoBidMax');
	const setAutoBidBtn = document.getElementById('setAutoBidBtn');

	// Charts
	const leaderboardCtx = document.getElementById('leaderboardChart');
	const bidHistoryCtx = document.getElementById('bidHistoryChart');
	const teams = window.AUCTION.teams || [];
	const teamNames = teams.map(t => t.name);
	const teamSpent = teams.map(t => Math.max(0, (t.budget_total||0) - (t.budget_remaining||0)));
	const leaderboardChart = new Chart(leaderboardCtx, { type: 'bar', data: { labels: teamNames, datasets: [{ label: 'Spent (₹)', data: teamSpent, backgroundColor: '#8b5cf6' }]}, options: {responsive: true, scales: { y: { beginAtZero: true }}}});
	const bidHistoryChart = new Chart(bidHistoryCtx, { type: 'line', data: { labels: [], datasets: [{ label: 'Bid (₹)', data: [], borderColor: '#6cf0ff'}]}, options: {responsive: true}});

	function fmt(n){ return '₹' + (n||0).toLocaleString('en-IN'); }
	function pushComment(text){
		const li = document.createElement('li');
		li.textContent = text;
		commentary.prepend(li);
	}
	function showPlayer(apId){
		const ap = players.find(p => p.id === apId) || players[0];
		if (!ap) return;
		current.apId = ap.id; current.playerId = ap.player_id;
		playerInfo.innerHTML = `<strong>${ap.player.name}</strong> — ${ap.player.role}<br/>Base: ${fmt(ap.player.base_price)}`;
		if (ap.player.highlight_url){ playerVideo.src = ap.player.highlight_url; playerVideo.style.display = 'block'; }
	}

	socket.on('connect', () => {
		socket.emit('join_auction', { auction_id: auctionId });
	});

	socket.on('snapshot', (snap) => {
		current.apId = snap.current_ap_id;
		current.highest = snap.highest_bid_amount || 0;
		current.highestTeamId = snap.highest_bid_team_id;
		current.end = snap.end_time ? new Date(snap.end_time) : null;
		currentBid.textContent = fmt(current.highest);
		bidHistoryChart.data.labels = snap.bid_history.map(b => new Date(b.ts).toLocaleTimeString());
		bidHistoryChart.data.datasets[0].data = snap.bid_history.map(b => b.amount);
		bidHistoryChart.update();
		if (current.apId) showPlayer(current.apId);
	});

	socket.on('player_start', (data) => {
		showPlayer(data.auction_player_id);
		pushComment('New player on the block!');
	});

	socket.on('tick', (data) => {
		countdown.textContent = data.remaining + 's';
		if (data.remaining <= 10) beep();
	});

	socket.on('bid_update', (data) => {
		current.highest = data.amount; current.highestTeamId = data.team_id;
		currentBid.textContent = fmt(current.highest);
		bidAmount.value = current.highest + 100000;
		gavel.classList.remove('drop');
		setTimeout(() => gavel.classList.add('drop'), 20);
		bidHistoryChart.data.labels.push(new Date().toLocaleTimeString());
		bidHistoryChart.data.datasets[0].data.push(current.highest);
		bidHistoryChart.update();
	});

	socket.on('player_sold', (data) => {
		pushComment(`SOLD for ${fmt(data.final_price || 0)} to Team ${data.sold_to_team_id || '-'}!`);
		gavel.classList.remove('drop'); setTimeout(()=> gavel.classList.add('drop'), 20);
		const idx = teams.findIndex(t => t.id === data.sold_to_team_id);
		if (idx >= 0){
			const t = teams[idx];
			const spent = Math.max(0, (t.budget_total||0) - (t.budget_remaining||0)) + (data.final_price||0);
			leaderboardChart.data.datasets[0].data[idx] = spent;
			leaderboardChart.update();
		}
		confetti();
	});

	socket.on('commentary', (msg) => pushComment(msg.text));

	function placeBid(){
		if (!teamId){ alert('Login as a team to bid'); return; }
		const amount = parseInt(bidAmount.value || '0');
		if (!current.playerId){ return; }
		socket.emit('place_bid', { auction_id: auctionId, team_id: teamId, amount: amount, player_id: current.playerId });
	}
	function enableAuto(){
		if (!teamId){ alert('Login as a team to bid'); return; }
		const max = parseInt(autoBidMax.value || '0');
		socket.emit('set_auto_bid', { auction_id: auctionId, team_id: teamId, max_limit: max });
	}

	placeBidBtn.addEventListener('click', placeBid);
	setAutoBidBtn.addEventListener('click', enableAuto);
	document.addEventListener('keydown', (e) => {
		if (e.key.toLowerCase() === 'b') placeBid();
		if (e.key.toLowerCase() === 'a') enableAuto();
	});

	// Simple confetti
	function confetti(){
		const el = document.createElement('canvas');
		el.className = 'confetti'; document.body.appendChild(el);
		const ctx = el.getContext('2d');
		el.width = innerWidth; el.height = innerHeight; const pieces = [];
		for (let i=0;i<180;i++){ pieces.push({x: Math.random()*el.width, y: -20, r: 6+Math.random()*6, c: `hsl(${Math.random()*360},90%,60%)`, s: 2+Math.random()*3}); }
		let t=0; const id = requestAnimationFrame(function loop(){
			ctx.clearRect(0,0,el.width, el.height);
			pieces.forEach(p=>{ p.y += p.s; p.x += Math.sin((p.y+p.r)/20); ctx.fillStyle=p.c; ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2); ctx.fill(); });
			if (++t < 200) requestAnimationFrame(loop); else document.body.removeChild(el);
		});
	}
	function beep(){
		try{
			const ctx = new (window.AudioContext||window.webkitAudioContext)();
			const o = ctx.createOscillator(); const g = ctx.createGain();
			o.type = 'sine'; o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
			g.gain.setValueAtTime(0.0001, ctx.currentTime);
			g.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.01);
			g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.15);
			o.start(); o.stop(ctx.currentTime + 0.16);
		}catch(e){}
	}
})();