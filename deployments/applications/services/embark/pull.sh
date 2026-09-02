#!/bin/sh
# Pulls each ModelKit listed in models.txt out of the cluster registry and
# unpacks it where embark expects to find it.
#
# Runs as embark's prestart task. embark resolves every model reference at
# startup and refuses to start on a missing one, so this has to finish before
# the server task begins, not race it.
#
# models.txt is generated from services/embark/models.json by services.tf and
# rendered into the task at /local/models.txt. One record per line:
#
#     <served-name> <full-registry-reference>
#
# Credentials come from a Docker-style auth file this task renders from Vault,
# so there is no `kit login` step and the password never becomes an argument.
#
# NOTE: this file is injected into a Nomad jobspec heredoc, which is parsed
# first by Nomad's HCL and then by consul-template. Neither a dollar sign
# followed by a brace nor a doubled brace may appear ANYWHERE in this file,
# comments included: both are template actions to those parsers and are eaten,
# or fail the parse, long before /bin/sh sees them. Plain $name expansion and
# $(command substitution) are fine.

set -eu

MODELS_FILE=/local/models.txt
# Nomad's secrets dir is a 1 MiB tmpfs, and --config is kit's ROOT storage
# directory, not just where credentials.json lives. That is safe only
# because unpack streams from the remote when a reference is absent from
# local storage, so nothing large is ever staged here. Adding a `kit pull`
# would fill it. The credential stays on tmpfs deliberately, rather than
# moving to the host volume where it would persist on disk.
KIT_CONFIG=/secrets/kit
ARTIFACT_ROOT=/var/lib/embark/artifacts

while read -r name ref; do
	# Skip blanks and comments so the generated file can carry either.
	[ -n "$name" ] || continue
	case "$name" in
	\#*) continue ;;
	esac

	dir="$ARTIFACT_ROOT/$name"
	marker="$dir/.ref"

	if [ -f "$marker" ] && [ "$(cat "$marker")" = "$ref" ]; then
		echo "model-pull: $name already at $ref"
		continue
	fi

	echo "model-pull: fetching $name from $ref"
	# Clear the marker BEFORE unpacking. A failed or interrupted unpack must
	# not leave a directory that claims to hold a model it does not, or the
	# next start would skip the pull and embark would fail on a partial
	# artifact. No marker means fetch again.
	rm -f "$marker"
	# </dev/null: this loop's stdin IS the model list, and kit inherits it.
	# A kit that reads a byte of stdin (a TTY probe, an auth prompt) would
	# swallow the remaining records and the script would exit 0 having
	# pulled only the first model.
	#
	# No --filter: it would unpack only layers under the Kitfile's `model`
	# field, and an embark artifact also needs tokenizer.json and
	# embark.json. Whether those sit in that layer depends on how the kit
	# was packed, and a filtered pull that drops them writes a .ref claiming
	# a complete artifact. These kits hold nothing but a model anyway.
	kit --config "$KIT_CONFIG" unpack "$ref" -d "$dir" --overwrite </dev/null
	printf '%s' "$ref" >"$marker"
done <"$MODELS_FILE"

echo "model-pull: done"
