/** Keep authored root-relative documentation links portable to project Pages. */
export default function remarkBase({ base }) {
  return (tree) => {
    function visit(node) {
      if (
        typeof node.url === "string" &&
        node.url.startsWith("/") &&
        !node.url.startsWith("//")
      ) {
        node.url = `${base}${node.url.slice(1)}`;
      }
      if (node.children) node.children.forEach(visit);
    }
    visit(tree);
  };
}
