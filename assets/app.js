// import { carouselFromSelector  } from "./carousel";
import Chart from 'chart.js/auto';
import 'chartjs-adapter-dayjs-4/dist/chartjs-adapter-dayjs-4.esm';

const MIN_QUERY_LENGTH = 3;

function debounce(func, wait, immediate) {
    let timeout;
    return function () {
        let context = this, args = arguments;
        let later = () => {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        let callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
};

var searchQuery = document.querySelector("#search-query");
var searchSuggestions = document.querySelector("#search-suggestions");
//var serverAlertEl = document.querySelector("#server-alert");
var trackDownloadProgressTimerID = null;

Videobox = {

    error: function(response) {
        return new Error(`Server returned error ${response.status} while handling request`);
    },

    downloadTorrent: function (url, template, event) {
        var formData = new FormData();
        formData.append('template', template)        
        fetch(url, { method: 'POST', body: formData })
            .then((response) => {
                if (!response.ok) {
                    throw Videobox.error(response);
                }
                response.text().then((text) => {
                    var buttonEl = event.target.closest('button');
                    buttonEl.outerHTML = text;
                    // Start updating page if needed 
                    // Videobox.trackDownloadProgress(Videobox.updateSeriesPage)
                });
            });
    },

    removeTorrent: function (url, event) {
        fetch(url, { method: 'DELETE' })
            .then((response) => {
                if (!response.ok) {
                    throw Videobox.error(response);
                }
                response.text().then((text) => {
                    var trEl = event.target.closest('tr');
                    trEl.remove();
                });
            });
    },

    followSeries: function (seriesId, newValue, event) {
        var formData = new FormData();
        formData.append('following', newValue)
        fetch(`/series/follow/${seriesId}`, { method: 'POST', body: formData })
            .then((response) => {
                if (!response.ok) {
                    throw Videobox.error(response);
                }
                response.text().then((text) => {
                    var buttonEl = event.target.closest('button');
                    buttonEl.outerHTML = text;
                });
            });
    },

    suggest: debounce(() => {
        var query = searchQuery.value;
        if (query.length < MIN_QUERY_LENGTH) {
            return;
        }
        fetch(`/suggest?query=${query}`)
            .then((response) => {
                if (!response.ok) {
                    throw Videobox.error(response);
                }
                response.text().then((text) => {
                    searchSuggestions.innerHTML = text;
                });
            });
    }, 200),

    sync: function () {
        var el = document.querySelector("#update-dialog");
        var eventSource = new EventSource("/sync/events");
        eventSource.addEventListener("sync-progress", (e) => {
            el.innerHTML = e.data;
        });
        eventSource.addEventListener("sync-done", (e) => {
            el.innerHTML = e.data;
            eventSource.close()
        });
        eventSource.addEventListener("error", (e) => {
            eventSource.close()
        });
    },

    openSearchDialog: function (event) {
        // Reset any previous search and suggestion - https://stackoverflow.com/a/65413839
        searchQuery.value = "";
        searchSuggestions.replaceChildren();
        Videobox.openDialog(event, '#search-dialog');
    },

    // closeDialog: function (event, dialogSelector) {
    //     var dialog = document.querySelector(dialogSelector);
    //     dialog.classList.remove("in");
    //     // TODO: wait for animation to end
    //     dialog.close();
    //     // Avoid to submit page
    //     event.preventDefault();
    // },

    openDialog: function (event, dialogSelector) {
        var dialog = document.querySelector(dialogSelector);
        dialog.showModal();
        // Close dialog when clicking on backdrop
        dialog.addEventListener('click', event => {
            if (event.target === event.currentTarget) {
                // dialog.replaceChildren();
                //dialog.innerHTML = '';
                event.currentTarget.close();
            }
        })
        return dialog;
    },

    trackDownloadProgress: function (callback, start = true) {
        if (start && trackDownloadProgressTimerID == null) {
            trackDownloadProgressTimerID = window.setInterval(() => {
                if (document.visibilityState == 'visible') {
                    fetch(`/download-progress`)
                        .then((response) => {
                            if (!response.ok) {
                                throw Videobox.error(response);
                            }
                            response.json().then((torrents) => {
                                callback(torrents);
                            });
                        });

                }
            },
                750 // ms
            )
        } else if (!start) {
            window.clearInterval(trackDownloadProgressTimerID);
        }
    },

    updateSeriesPage: function (torrents) {
        torrents.forEach(torrent => {
            // Update release table
            var trEl = document.getElementById(`r${torrent['info_hash']}`);
            // No need to keep updating status if already downloaded
            if (trEl && trEl.dataset.status != 'D') {
                trEl.querySelector('.releases__download').innerHTML = `<span class="text-accent text-sm">${torrent['progress']}%</span>`;
            }

            // Update release dialog
            var progressEl = document.getElementById(`download-progress-${torrent['info_hash']}`);
            if (progressEl) {
                progressEl.querySelector('.download-progress__stats').innerHTML = torrent['stats']
                progressEl.querySelector('progress').setAttribute('value', torrent['progress']);
            }
        })
    },

    updateStatusPage: function (torrents) {
        torrents.forEach(torrent => {
            // Update downloads table row
            var trEl = document.getElementById(`r${torrent['info_hash']}`);
            // No need to keep updating status if already downloaded
            if (trEl && trEl.dataset.status != 'D') {
                trEl.querySelector('.download-progress__stats').innerHTML = torrent['stats'];
                trEl.querySelector('progress').setAttribute('value', torrent['progress']);
            }
        })
    },

    loadSettings: function (event) {
        var dialog = Videobox.openDialog(event, '#dialog');
        fetch("/settings")
            .then((response) => {
                if (!response.ok) {
                    throw Videobox.error(response);
                }
                response.text().then((text) => {
                    dialog.innerHTML = text;
                });
            });
    },

    loadReleaseInfo: function (event, releaseId) {
        var dialog = Videobox.openDialog(event, '#dialog');
        fetch(`/release/${releaseId}`)
            .then((response) => {
                if (!response.ok) {
                    throw Videobox.error(response);
                }
                response.text().then((text) => {
                    dialog.innerHTML = text;
                });
            });
    },

    loadMore: function (url) {
        var wrapper = document.querySelector(".load-more-wrapper");
        fetch(url)
            .then((response) => {
                if (!response.ok) {
                    throw Videobox.error(response);
                }
                response.text().then((text) => {
                    var button = wrapper.querySelector("button");
                    button.remove();
                    var template = document.createElement('template');
                    template.innerHTML = text;
                    var child = wrapper.appendChild(template.content.firstElementChild);
                    child.scrollIntoView({ behavior: "smooth", block: "start" })
                });
            });
    },

    filterSeries: function (form, event) {
        var wrapper = document.querySelector(".episode-wrapper");
        var formData = new FormData(form);
        formData.append('async', "1");
        const queryString = new URLSearchParams(formData).toString()
        var url = form.getAttribute('action');
        event.preventDefault();
        fetch(`${url}?${queryString}`)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Server returned error ${response.status} while handling request`);
                }
                response.text().then((text) => {
                    wrapper.innerHTML = text;   
                });
            });
        // @@TODO Push nav history?
        // history.pushState({}, "", url);
    },

    loadChart: function (el) {
        const dailyCounts = chartData.map(item => { return { x: item.date, y: item.count } });
        var ctx = el.getContext('2d');
        const chart = new Chart(el, {
            data: {
                datasets: [{
                    type: 'line',
                    data: dailyCounts,
                    fill: true,
                    pointBorderColor: '#e37dd7',
                    pointBackgroundColor: '#fff',
                    pointBorderWidth: 0,
                    borderColor: '#e37dd7',
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHitRadius: 2,
                    backgroundColor: '#253e52',

                }
                ]
            },
            options: {
                layout: {
                    padding: -10
                },                
                plugins: {
                    legend: {
                        display: false
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { display: false },
                        type: 'time',
                        time: {
                            unit: 'week',
                            tooltipFormat: 'MMM D, YYYY',
                        }
                    },
                    y: {                        
                        beginAtZero: true,
                        grid: { display: false },
                        ticks: { display: false },
                    }
                }
            }
        });
    },
    setup: function() {
        // var carousels = carouselFromSelector('.carousel__items');
        var filtersEl = document.getElementById('form-filters');
        if(filtersEl) {
            const observer = new IntersectionObserver( 
                // Check if pinned or not 
                ([e]) => e.target.classList.toggle("pinned", e.intersectionRatio < 1),
                { threshold: [1] }
              );
            observer.observe(filtersEl);
        }
    }
}

Videobox.setup();