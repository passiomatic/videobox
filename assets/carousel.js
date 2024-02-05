export { Carousel, carouselFromSelector };
// An "almost pure" CSS image carousel.
//
// See:
//  * https://css-tricks.com/can-get-pretty-far-making-slider-just-html-css/
//  * https://stackoverflow.com/a/58386348

const ITEM_CLASS = "carousel-item";

// Create multiple slider instances given an element selector
function carouselFromSelector(selector, options) {
  const elements = Array.from(document.querySelectorAll(selector));
  return elements.map((element) => {
    return new Carousel(element, options);
  });
}

const defaultOptions = {
  itemClass: ITEM_CLASS,
  // Called when user requested a new item to be shown
  onItemChange: function (item, index) { }
};

const scrollOptions = {
  behavior: "smooth",
  block: "end",
  inline: "center"
}

// Create a new Carousel instance using the DOM element passed as argument
//   (most likely an element with the "carousel" CSS class)
function Carousel(element, options) {

  if (typeof element.carousel !== "undefined") {
    // Already initialized
    return;
  }

  if (!options) {
    options = defaultOptions;
  }

  var activeIndex = 0;
  var items = Array.from(element.querySelectorAll(`.${options.itemClass}`));
  const prevEl = element.querySelector("[data-nav=prev]");
  const nextEl = element.querySelector("[data-nav=next]");

  const observer = new IntersectionObserver(_handleIntersect, {
    root: element,
    rootMargin: "0px",
    threshold: 1,
  });

  items.forEach((el, index) => {
    observer.observe(el);
  });  

  function _updateNav() {
    if (prevEl && prevEl) {
      prevEl.style.opacity = 0.7;
      nextEl.style.opacity = 0.7;

      if (activeIndex > 0) {
        prevEl.style.opacity = 1.0;
      }
      if (activeIndex < items.length - 1) {
        nextEl.style.opacity = 1.0;
      }
    }
  }

  function _handleIntersect(entries) {
    items.forEach((item) => { item.classList.remove("active") })
    // Transitioning into a fully visible state 
    var fullyVisibleEntries = entries.filter((entry) => entry.isIntersecting);
    var prevX = 9999;
    fullyVisibleEntries.forEach((entry, index) => {
      // console.log(`boundingClientRect #${index}`, entry.boundingClientRect)
      entry.target.classList.add("active");
      // if(prevX > entry.boundingClientRect.x) {
      //   prevX = entry.boundingClientRect.x;
      //   items.forEach((item) => { item.classList.remove("active") })
      //   // Find index for current active slide
      //   activeIndex = items.findIndex((e) => { e === entry.target });
      //   _updateNav();
      // } 
    })
  }

  function _prev(event) {
    if (activeIndex > 0) {
      items[activeIndex - 1].scrollIntoView(scrollOptions);
      options.onItemChange(el, activeIndex - 1);
    }
  }

  function _next(event) {
    if (activeIndex < items.length - 1) {
      items[activeIndex + 1].scrollIntoView(scrollOptions);
      options.onItemChange(el, activeIndex + 1);
    }
  }

  _updateNav();

  // Hook prev/next buttons if any
  if (prevEl) {
    prevEl.addEventListener("click", _prev);
  }
  if (nextEl) {
    nextEl.addEventListener("click", _next);
  }

  // Attach instance to DOM node
  element.carousel = this;
}
