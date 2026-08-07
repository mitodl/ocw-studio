// Webpack inlines svg icons as raw strings via raw-loader, so tests need real
// svg markup rather than a filename stub. CKEditor's IconView parses this as
// XML and dereferences the root <svg>, which throws on a plain string.
module.exports =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"></svg>'
