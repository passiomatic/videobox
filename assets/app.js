// import { carouselFromSelector  } from "./carousel";
import htmx from 'htmx.org';

function addDialogCloseListener(dialogEl) {
    dialogEl.addEventListener('click', event => {
        if (event.target === event.currentTarget) {
            event.currentTarget.close();
        } else if ('close' in event.target.dataset) {
            dialog.close();
        }
    })
}

var trackDownloadProgressTimerID = null;

Videobox = {

    error: function (response) {
        return new Error(`Server returned error ${response.status} while handling request`);
    },

    openSearchDialog: function (event) {
        // Reset any previous search and suggestion
        let searchQuery = document.querySelector("#search-query");
        searchQuery.value = "";
        let searchSuggestions = document.querySelector("#search-suggestions");
        searchSuggestions.replaceChildren();
        Videobox.openDialog(event, '#search-dialog');
    },

    openDialog: function (event, dialogSelector) {
        let dialogEl = document.querySelector(dialogSelector);
        if (dialogEl) {
            dialogEl.showModal();
            addDialogCloseListener(dialogEl);
            return dialogEl;
        } else {
            throw new Error(`Dialog element not found for selector: ${dialogSelector}`);
        }
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
            trackDownloadProgressTimerID = null;
        }
    },

    updateSeriesPage: function (torrents) {
        var templateDone = document.getElementById("row-download-done");
        if (templateDone) {
            torrents.forEach(torrent => {
                // Update release table
                var trEl = document.getElementById(`r${torrent['info_hash']}`);
                if (trEl) {
                    var tdEl = trEl.querySelector('.releases__download');
                    if (trEl.dataset.status == 'D') {
                        // Already downloaded, do nothing
                    } else if (torrent['state'] == 'D') {
                        // Just downloaded
                        var clonedEl = templateDone.content.cloneNode(true);
                        tdEl.replaceChildren(clonedEl);
                    } else {
                        // In progress, avoid to replace children
                        //  to keep the ongoing CSS animation
                        var spanEl = tdEl.querySelector("span");
                        if (spanEl) {
                            spanEl.textContent = `${torrent['progress']}%`;
                        }
                    }
                }

                // Update release dialog
                var progressEl = document.getElementById(`download-progress-${torrent['info_hash']}`);
                if (progressEl) {
                    progressEl.querySelector('.download-progress__stats').innerHTML = torrent['stats']
                    progressEl.querySelector('progress').setAttribute('value', torrent['progress']);
                }
            })
        }
    },

    setup: function () {
        // var carousels = carouselFromSelector('.carousel__items');
        let filtersEl = document.getElementById('form-filters');
        if (filtersEl) {
            const observer = new IntersectionObserver(
                // Check if pinned or not 
                ([e]) => e.target.classList.toggle("pinned", e.intersectionRatio < 1),
                { threshold: [1] }
            );
            observer.observe(filtersEl);
        }

        window.addEventListener("popstate", (event) => {
            // Reload page on back/forward navigation
            location.reload();
        });

        // Setup HTML5 dialog to work with htmx 
        // https://blog.benoitblanchon.fr/django-htmx-modal-form/
        let dialogEl = document.getElementById("dialog");
        htmx.on("htmx:afterSwap", (e) => {
            // Only response targeting dialog
            if (e.detail.target.id == "dialog") {
                dialogEl.showModal();
            }
        })

        htmx.on("htmx:beforeSwap", (e) => {
            // Empty response targeting #dialog
            if (e.detail.target.id == "dialog" && !e.detail.xhr.response) {
                dialogEl.close();
                e.detail.shouldSwap = false;
            }
        })

        addDialogCloseListener(dialogEl);
    }
}

Videobox.setup();