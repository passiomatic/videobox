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

Videobox = {

    followSeries: function (seriesId, newValue, event) {
        var formData = new FormData();
        formData.append('following', newValue)
        fetch(`/series/follow/${seriesId}`, { method: 'POST', body: formData })
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Server returned error ${response.status} while handling POST request`);
                }
                response.text().then((text) => {
                    var button = event.target.closest('button');
                    button.outerHTML = text;
                });
            });
    },

    suggest: debounce(() => {
        var query = searchQuery.value;
        if (query.length <= MIN_QUERY_LENGTH) {
            return;
        }
        fetch(`/suggest?query=${query}`)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Server returned error ${response.status} while handling suggest query`);
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
        dialog.classList.add("in");
        // Close dialog when clicking on backdrop
        dialog.addEventListener('click', event => {
            if (event.target === event.currentTarget) {
                event.currentTarget.close();
            }
        })
        return dialog;
    },

    loadReleaseInfo: function (event, releaseId) {
        var dialog = Videobox.openDialog(event, '#release-dialog');
        fetch(`/release/${releaseId}`)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Server returned error ${response.status} while handling request`);
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
                    throw new Error(`Server returned error ${response.status} while handling tag pagination`);
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
        var gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(49,93,124,0.9)');
        gradient.addColorStop(1, 'rgba(49,93,124,0.1)');
        const chart = new Chart(el, {
            data: {
                datasets: [{
                    type: 'line',
                    // showLine: false,
                    // label: 'Daily Releases',
                    data: dailyCounts,
                    fill: true,
                    pointBorderColor: '#e37dd7',
                    pointBackgroundColor: '#fff',
                    pointBorderWidth: 1,
                    borderColor: '#e37dd7',
                    borderWidth: 2,
                    backgroundColor: gradient, //'#315d7c',
                    borderJoinStyle: 'round'
                }
                ]
            },
            options: {
                plugins: {
                    legend: {
                        display: false
                        // labels: {
                        //     color: "#9dc5e0",
                        // },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "#2a6278" },
                        ticks: { color: "#9dc5e0" },
                        type: 'time',
                        time: {
                            unit: 'week'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "#2a6278" },
                        ticks: { color: "#9dc5e0" },
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