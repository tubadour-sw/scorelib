/* Erfordert, dass jQuery im Admin geladen ist */
django.jQuery(document).ready(function() {
    django.jQuery('#id_concert').change(function() {
        var concertId = django.jQuery(this).val();
        
        // Aktuelle URL prüfen
        var urlParams = new URLSearchParams(window.location.search);
        var currentUrlConcert = urlParams.get('concert');

        // Nur neu laden, wenn die ID im Feld anders ist als in der URL
        if (concertId && concertId !== currentUrlConcert) {
            var currentUrl = window.location.origin + window.location.pathname;
            window.location.href = currentUrl + '?concert=' + concertId;
        }
    });
});