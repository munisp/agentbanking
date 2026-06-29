import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import React, { useState } from "react";
import {
    Alert,
    Image,
    KeyboardAvoidingView,
    Modal,
    Platform,
    ScrollView,
    StyleSheet,
    TouchableOpacity,
    View,
} from "react-native";
import {
    Button,
    Card,
    Menu,
    Snackbar,
    Text,
    TextInput,
    useTheme} from "react-native-paper";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { documentApi, inventoryApi } from "../../services/apiService";
import { spacing } from "../../theme";
const CATEGORIES = [
  "Hardware",
  "Software",
  "Electronics",
  "Mobile Devices",
  "Accessories",
  "Services",
  "Other",
];

const LOCATIONS = [
  "Warehouse A",
  "Warehouse B",
  "Store Front",
  "Back Room",
  "Display",
];

export default function AddInventoryItemScreen({
 route, navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const theme = useTheme();
  const { storeId } = route.params || {};

  const [formData, setFormData] = useState({
    name: "",
    sku: "",
    category: "Hardware",
    quantity: "0",
    reorder_level: "10",
    unit_price: "",
    supplier: "",
    location: "Warehouse A",
    barcode: "",
  });

  const [permission, requestPermission] = useCameraPermissions();
  const [showBarcodeScanner, setShowBarcodeScanner] = useState(false);
  const [barcodeScanned, setBarcodeScanned] = useState(false);

  const [uploadedImages, setUploadedImages] = useState([]);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [categoryMenuVisible, setCategoryMenuVisible] = useState(false);
  const [locationMenuVisible, setLocationMenuVisible] = useState(false);

  const updateField = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleBarcodeScanned = ({ type, data }) => {
    setBarcodeScanned(true);
    updateField("barcode", data);
    setShowBarcodeScanner(false);
    setBarcodeScanned(false);
    setSuccess(`Barcode scanned: ${data}`);
  };

  const openBarcodeScanner = async () => {
    if (!permission) {
      const result = await requestPermission();
      if (!result.granted) {
        Alert.alert(
          "Permission Required",
          "Camera permission is required to scan barcodes",
        );
        return;
      }
    }
    if (!permission?.granted) {
      const result = await requestPermission();
      if (!result.granted) {
        Alert.alert(
          "Permission Required",
          "Camera permission is required to scan barcodes",
        );
        return;
      }
    }
    setBarcodeScanned(false);
    setShowBarcodeScanner(true);
  };

  const requestCameraPermission = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission Required",
        "Camera permission is required to take photos",
      );
      return false;
    }
    return true;
  };

  const requestMediaLibraryPermission = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission Required",
        "Media library permission is required to select photos",
      );
      return false;
    }
    return true;
  };

  const handleTakePhoto = async () => {
    const hasPermission = await requestCameraPermission();
    if (!hasPermission) return;

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ["images"],
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
      // Try PNG format for better compatibility
      base64: false,
      exif: false,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      await uploadImage(result.assets[0]);
    }
  };

  const handlePickImage = async () => {
    const hasPermission = await requestMediaLibraryPermission();
    if (!hasPermission) return;

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      for (const asset of result.assets) {
        await uploadImage(asset);
      }
    }
  };

  const uploadImage = async (asset) => {
    const id = `${Date.now()}-${Math.random()}`;
    const previewUrl = asset.uri;
    const fileName = asset.uri.split("/").pop();

    // Add placeholder
    setUploadedImages((prev) => [
      ...prev,
      { id, previewUrl, docUrl: null, uploading: true, name: fileName },
    ]);

    setUploadingImages(true);

    try {
      // Detect file type from URI extension
      const uri = asset.uri.toLowerCase();
      let mimeType = asset.type || "image/jpeg";
      let defaultName = `photo_${Date.now()}.jpg`;

      if (uri.endsWith(".png")) {
        mimeType = "image/png";
        defaultName = `photo_${Date.now()}.png`;
      } else if (uri.endsWith(".jpg") || uri.endsWith(".jpeg")) {
        mimeType = "image/jpeg";
        defaultName = `photo_${Date.now()}.jpg`;
      }

      // Create file object for upload
      const file = {
        uri: asset.uri,
        type: mimeType,
        name: fileName || defaultName,
      };

      console.log("Uploading file:", {
        uri: file.uri,
        type: file.type,
        name: file.name,
      });

      const resp = await documentApi.uploadFile(file, "product_image");
      console.log("Upload response:", resp);

      let imageUrl = resp.url;
      if (imageUrl && !imageUrl.startsWith("http")) {
        imageUrl = `https://${imageUrl}`;
      }

      console.log("Stored image URL:", imageUrl);

      setUploadedImages((prev) =>
        prev.map((img) =>
          img.id === id ? { ...img, docUrl: imageUrl, uploading: false } : img,
        ),
      );
    } catch (err) {
      console.error("Upload failed:", fileName, err);
      setUploadedImages((prev) => prev.filter((img) => img.id !== id));
      setError(`Failed to upload "${fileName}": ${err.message || err}`);
    } finally {
      setUploadingImages(false);
    }
  };

  const removeImage = (id) => {
    setUploadedImages((prev) => prev.filter((img) => img.id !== id));
  };

  const showImageOptions = () => {
    Alert.alert("Add Image", "Choose an option", [
      {
        text: "Take Photo",
        onPress: handleTakePhoto,
      },
      {
        text: "Choose from Library",
        onPress: handlePickImage,
      },
      {
        text: "Cancel",
        style: "cancel",
      },
    ]);
  };

  const validateForm = () => {
    if (!formData.name.trim()) {
      setError("Item name is required");
      return false;
    }
    if (!formData.sku.trim()) {
      setError("SKU is required");
      return false;
    }
    if (!formData.unit_price || parseFloat(formData.unit_price) <= 0) {
      setError("Valid unit price is required");
      return false;
    }
    if (!storeId) {
      setError("Store ID is missing");
      return false;
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    if (uploadingImages) {
      setError("Please wait for images to finish uploading");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const itemData = {
        ...formData,
        quantity: parseInt(formData.quantity) || 0,
        reorder_level: parseInt(formData.reorder_level) || 10,
        unit_price: parseFloat(formData.unit_price),
        store_id: storeId,
      };

      console.log("Creating item:", itemData);
      const createdItem = await inventoryApi.createInventoryItem(
        storeId,
        itemData,
      );
      console.log("Created item:", createdItem);

      // Associate images
      const readyImages = uploadedImages.filter((i) => i.docUrl);
      console.log("Images to associate:", readyImages.length, readyImages);

      for (const img of readyImages) {
        try {
          console.log(
            "Associating image URL:",
            img.docUrl,
            "with item:",
            createdItem.id,
          );
          await inventoryApi.addItemImageUrl(createdItem.id, img.docUrl);
        } catch (e) {
          console.error("Failed to link image:", img.docUrl, e);
          setError(`Warning: Failed to link image: ${e.message || e}`);
        }
      }

      setSuccess("Item added successfully!");
      setTimeout(() => {
        navigation.goBack();
      }, 1500);
    } catch (err) {
      console.error("Error adding item:", err);
      setError(err.message || "Failed to add item");
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.container}
    >
      <ScrollView style={styles.scrollView}>
        <View style={styles.content}>
          {/* Header */}
          <View style={styles.header}>
            <Icon
              name="package-variant-closed"
              size={32}
              color={theme.colors.primary}
            />
            <Text variant="headlineSmall" style={styles.headerText}>
              Add Inventory Item
            </Text>
          </View>

          {/* Basic Information */}
          <Card style={styles.section}>
            <Card.Content>
              <Text variant="titleMedium" style={styles.sectionTitle}>
                Basic Information
              </Text>

              <TextInput
                label="Item Name *"
                value={formData.name}
                onChangeText={(text) => updateField("name", text)}
                mode="outlined"
                style={styles.input}
                placeholder="e.g., HP Laptop 15"
              />

              <TextInput
                label="SKU *"
                value={formData.sku}
                onChangeText={(text) => updateField("sku", text)}
                mode="outlined"
                style={styles.input}
                placeholder="e.g., HP-LAPTOP-001"
              />

              <Menu
                visible={categoryMenuVisible}
                onDismiss={() => setCategoryMenuVisible(false)}
                anchor={
                  <TouchableOpacity
                    onPress={() => setCategoryMenuVisible(true)}
                  >
                    <TextInput
                      label="Category"
                      value={formData.category}
                      mode="outlined"
                      style={styles.input}
                      editable={false}
                      right={<TextInput.Icon icon="chevron-down" />}
                    />
                  </TouchableOpacity>
                }
              >
                {CATEGORIES.map((cat) => (
                  <Menu.Item
                    key={cat}
                    onPress={() => {
                      updateField("category", cat);
                      setCategoryMenuVisible(false);
                    }}
                    title={cat}
                  />
                ))}
              </Menu>

              <TextInput
                label="Barcode (Optional)"
                value={formData.barcode}
                onChangeText={(text) => updateField("barcode", text)}
                mode="outlined"
                style={styles.input}
                placeholder="e.g., 1234567890123"
                right={
                  <TextInput.Icon
                    icon="barcode-scan"
                    onPress={openBarcodeScanner}
                  />
                }
              />
            </Card.Content>
          </Card>

          {/* Stock & Pricing */}
          <Card style={styles.section}>
            <Card.Content>
              <Text variant="titleMedium" style={styles.sectionTitle}>
                Stock & Pricing
              </Text>

              <View style={styles.row}>
                <TextInput
                  label="Quantity"
                  value={formData.quantity}
                  onChangeText={(text) => updateField("quantity", text)}
                  mode="outlined"
                  style={[styles.input, styles.halfInput]}
                  keyboardType="numeric"
                />

                <TextInput
                  label="Reorder Level"
                  value={formData.reorder_level}
                  onChangeText={(text) => updateField("reorder_level", text)}
                  mode="outlined"
                  style={[styles.input, styles.halfInput]}
                  keyboardType="numeric"
                />
              </View>

              <TextInput
                label="Unit Price (₦) *"
                value={formData.unit_price}
                onChangeText={(text) => updateField("unit_price", text)}
                mode="outlined"
                style={styles.input}
                keyboardType="decimal-pad"
                placeholder="e.g., 250000"
              />

              <TextInput
                label="Supplier (Optional)"
                value={formData.supplier}
                onChangeText={(text) => updateField("supplier", text)}
                mode="outlined"
                style={styles.input}
                placeholder="e.g., Tech Solutions Ltd"
              />

              <Menu
                visible={locationMenuVisible}
                onDismiss={() => setLocationMenuVisible(false)}
                anchor={
                  <TouchableOpacity
                    onPress={() => setLocationMenuVisible(true)}
                  >
                    <TextInput
                      label="Location"
                      value={formData.location}
                      mode="outlined"
                      style={styles.input}
                      editable={false}
                      right={<TextInput.Icon icon="chevron-down" />}
                    />
                  </TouchableOpacity>
                }
              >
                {LOCATIONS.map((loc) => (
                  <Menu.Item
                    key={loc}
                    onPress={() => {
                      updateField("location", loc);
                      setLocationMenuVisible(false);
                    }}
                    title={loc}
                  />
                ))}
              </Menu>
            </Card.Content>
          </Card>

          {/* Product Images */}
          <Card style={styles.section}>
            <Card.Content>
              <Text variant="titleMedium" style={styles.sectionTitle}>
                Product Images (Optional)
              </Text>

              <Button
                mode="outlined"
                onPress={showImageOptions}
                icon="camera"
                style={styles.addImageButton}
                disabled={uploadingImages}
              >
                {uploadingImages ? "Uploading..." : "Add Image"}
              </Button>

              {uploadedImages.length > 0 && (
                <View style={styles.imageGrid}>
                  {uploadedImages.map((img) => (
                    <View key={img.id} style={styles.imageContainer}>
                      <Image
                        source={{ uri: img.previewUrl }}
                        style={styles.imagePreview}
                        resizeMode="cover"
                        onError={(error) => {
                          console.error("Image load error:", error);
                          removeImage(img.id);
                        }}
                      />

                      {img.uploading ? (
                        <View style={styles.uploadingOverlay}>
                          <Icon name="loading" size={24} color="#fff" />
                          <Text style={styles.uploadingText}>Uploading</Text>
                        </View>
                      ) : img.docUrl ? (
                        <TouchableOpacity
                          style={styles.removeImageButton}
                          onPress={() => removeImage(img.id)}
                        >
                          <Icon name="close-circle" size={24} color="#EF4444" />
                        </TouchableOpacity>
                      ) : (
                        <View style={styles.errorOverlay}>
                          <Text style={styles.errorText}>Failed</Text>
                        </View>
                      )}
                    </View>
                  ))}
                </View>
              )}

              {uploadedImages.length > 0 && !uploadingImages && (
                <Text variant="bodySmall" style={styles.imageCount}>
                  {uploadedImages.filter((i) => i.docUrl).length} of{" "}
                  {uploadedImages.length} image(s) ready
                </Text>
              )}
            </Card.Content>
          </Card>

          {/* Submit Buttons */}
          <View style={styles.buttonContainer}>
            <Button
              mode="contained"
              onPress={handleSubmit}
              loading={loading}
              disabled={loading || uploadingImages}
              style={styles.submitButton}
              buttonColor={theme.colors.primary}
            >
              {uploadingImages
                ? "Waiting for images…"
                : loading
                  ? "Adding…"
                  : "Add Item"}
            </Button>

            <Button
              mode="outlined"
              onPress={() => navigation.goBack()}
              style={styles.cancelButton}
              disabled={loading}
            >
              Cancel
            </Button>
          </View>
        </View>
      </ScrollView>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={3000}
        action={{
          label: "Dismiss",
          onPress: () => setError(""),
        }}
      >
        {error}
      </Snackbar>

      <Snackbar
        visible={!!success}
        onDismiss={() => setSuccess("")}
        duration={1500}
        style={{ backgroundColor: "#10B981" }}
      >
        {success}
      </Snackbar>

      {/* Barcode Scanner Modal */}
      <Modal
        visible={showBarcodeScanner}
        animationType="slide"
        onRequestClose={() => setShowBarcodeScanner(false)}
      >
        <View style={styles.scannerContainer}>
          <CameraView
            style={styles.camera}
            onBarcodeScanned={barcodeScanned ? undefined : handleBarcodeScanned}
            barcodeScannerSettings={{
              barcodeTypes: [
                "ean13",
                "ean8",
                "upc_a",
                "upc_e",
                "code39",
                "code128",
                "qr",
              ],
            }}
          >
            <View style={styles.scannerOverlay}>
              <View style={styles.scannerHeader}>
                <Text variant="headlineSmall" style={styles.scannerTitle}>
                  Scan Barcode
                </Text>
                <Button
                  mode="text"
                  onPress={() => setShowBarcodeScanner(false)}
                  textColor="#fff"
                >
                  Cancel
                </Button>
              </View>
              <View style={styles.scanArea}>
                <View style={[styles.corner, styles.topLeft]} />
                <View style={[styles.corner, styles.topRight]} />
                <View style={[styles.corner, styles.bottomLeft]} />
                <View style={[styles.corner, styles.bottomRight]} />
              </View>
              <Text variant="bodyLarge" style={styles.scannerInstruction}>
                Position barcode within frame
              </Text>
            </View>
          </CameraView>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  headerText: {
    fontWeight: "600",
  },
  section: {
    marginBottom: spacing.md,
  },
  sectionTitle: {
    marginBottom: spacing.md,
    fontWeight: "600",
    color: "#111827",
  },
  input: {
    marginBottom: spacing.sm,
    backgroundColor: "#fff",
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  halfInput: {
    flex: 1,
  },
  addImageButton: {
    marginBottom: spacing.md,
  },
  imageGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  imageContainer: {
    width: "48%",
    aspectRatio: 1,
    position: "relative",
    borderRadius: 8,
    overflow: "hidden",
    backgroundColor: "#F3F4F6",
  },
  imagePreview: {
    width: "100%",
    height: "100%",
    backgroundColor: "#F3F4F6",
  },
  uploadingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
  },
  uploadingText: {
    color: "#fff",
    fontSize: 12,
    marginTop: spacing.xs,
  },
  removeImageButton: {
    position: "absolute",
    top: -8,
    right: -8,
    backgroundColor: "#fff",
    borderRadius: 12,
  },
  errorOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(239, 68, 68, 0.6)",
    justifyContent: "center",
    alignItems: "center",
  },
  errorText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "600",
  },
  imageCount: {
    color: "#6B7280",
    marginTop: spacing.xs,
  },
  buttonContainer: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  submitButton: {
    paddingVertical: spacing.xs,
  },
  cancelButton: {
    paddingVertical: spacing.xs,
  },
  scannerContainer: {
    flex: 1,
    backgroundColor: "#000",
  },
  camera: {
    flex: 1,
  },
  scannerOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
  },
  scannerHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xl,
    paddingBottom: spacing.md,
  },
  scannerTitle: {
    color: "#fff",
    fontWeight: "600",
  },
  scanArea: {
    width: 280,
    height: 180,
    alignSelf: "center",
    marginTop: "30%",
    position: "relative",
  },
  corner: {
    position: "absolute",
    width: 40,
    height: 40,
    borderColor: "#fff",
  },
  topLeft: {
    top: 0,
    left: 0,
    borderTopWidth: 4,
    borderLeftWidth: 4,
  },
  topRight: {
    top: 0,
    right: 0,
    borderTopWidth: 4,
    borderRightWidth: 4,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
  },
  scannerInstruction: {
    color: "#fff",
    textAlign: "center",
    marginTop: spacing.xl,
  },
});
