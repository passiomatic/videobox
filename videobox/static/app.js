const MIN_QUERY_LENGTH = 3;
window.addEventListener("DOMContentLoaded", (event) => {

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

        suggest: debounce(() => {
            var query = searchQuery.value;
            if (query.length < MIN_QUERY_LENGTH) {
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

        update: function () {
            var dialog = this.openDialog(event, "#update-dialog")
            fetch("/update")
                .then((response) => {
                    if (!response.ok) {
                        throw new Error(`Server returned error ${response.status} while handling update`);
                    }
                });
            var eventSource = new EventSource("/update-events");
            eventSource.addEventListener("updating", (e) => {
                dialog.innerHTML = e.data;
            });
            eventSource.addEventListener("done", (e) => {
                dialog.innerHTML = e.data;
                eventSource.close()
            });
            eventSource.addEventListener("error", (e) => {
                eventSource.close()
            });
        },
    
        openSearchDialog: function(event) {
            // Reset any previosu search and suggestion - https://stackoverflow.com/a/65413839
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
            var wrapper = document.querySelector(".cards-grid-wrapper");
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
        }
    }
})