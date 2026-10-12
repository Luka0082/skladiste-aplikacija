// Interaktivno pretraživanje i filtriranje skladišta
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchWarehouse');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            const query = this.value.toLowerCase();
            const cards = document.querySelectorAll('.sektor-card');

            cards.forEach(card => {
                const text = card.textContent.toLowerCase();
                if (text.includes(query)) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }
});

function prikaziDetalje(lokacijaId, sektor, regal, polica) {
    const modal = document.getElementById('detailsModal');
    const title = document.getElementById('modalTitle');
    
    if (modal && title) {
        title.innerText = `Detaljan pregled: Sektor ${sektor} - Regal ${regal} (Polica ${polica})`;
        modal.style.display = 'block';
    }
}

function zatvoriModal() {
    const modal = document.getElementById('detailsModal');
    if (modal) {
        modal.style.display = 'none';
    }
}